import collections

import numpy as np

from libertem.udf import UDF


VariancePart = collections.namedtuple('VariancePart', ['var', 'sum_im', 'N'])


def merge(p0, p1):
    """
    Given two sets of partitions, with sum of frames
    and sum of variances, compute joint sum of frames
    and sum of variances using one pass algorithm

    Parameters
    ----------
    p0
        Contains information about the first partition, including
        sum of variances, sum of pixels, and number of frames used

    p1
        Contains information about the second partition, including
        sum of variances, sum of pixels, and number of frames used

    Returns
    -------
    VariancePart
        colletions.namedtuple object that contains information about
        the merged partitions, including sum of variances,
        sum of pixels, and number of frames used
    """
    if p0.N == 0:
        return p1
    N = p0.N + p1.N

    # compute mean for each partitions
    mean_A = (p0.sum_im / p0.N)
    mean_B = (p1.sum_im / p1.N)

    # compute mean for joint samples
    delta = mean_B - mean_A
    mean = mean_A + (p1.N * delta) / (p0.N + p1.N)

    # compute sum of images for joint samples
    sum_im_AB = p0.sum_im + p1.sum_im

    # compute sum of variances for joint samples
    delta_P = mean_B - mean
    var_AB = p0.var + p1.var + (p1.N * delta * delta_P)

    return VariancePart(var=var_AB, sum_im=sum_im_AB, N=N)


# Helper function to make sure the frame count
# is consistent at the merge stage
def _validate_n(num_frame):
    if len(num_frame) == 0:
        return 0
    else:
        values = tuple(num_frame.values())
        assert np.all(np.equal(values, values[0]))
        return values[0]


class StdDevUDF(UDF):
    """
    Compute sum of variances and sum of pixels from the given dataset

    One-pass algorithm used in this code is taken from the following paper:
    "Numerically Stable Parallel Computation of (Co-) Variance"
    DOI : https://doi.org/10.1145/3221269.3223036

    Examples
    --------

    >>> udf = StdDevUDF()
    >>> result = ctx.run_udf(dataset=dataset, udf=udf)
    >>> # Note: These are raw results. Use run_stddev() instead of
    >>> # using the UDF directly to obtain
    >>> # variance, standard deviation and mean
    >>> np.array(result["var"])        # variance times number of frames
    array(...)
    >>> np.array(result["num_frame"])  # number of frames
    array(...)
    >>> np.array(result["sum_frame"])  # sum of all frames
    array(...)
    """

    def get_result_buffers(self):
        """
        Initializes BufferWrapper objects for sum of variances,
        sum of frames, and the number of frames

        Returns
        -------
        A dictionary that maps 'var', 'std', 'mean', 'num_frame', 'sum_frame' to
        the corresponding BufferWrapper objects
        """
        return {
            'var': self.buffer(
                kind='sig', dtype='float32'
            ),
            'num_frame': self.buffer(
                kind='single', dtype='object'
            ),
            'sum_frame': self.buffer(
                kind='sig', dtype='float32'
            )
        }

    def preprocess(self):
        self.results.num_frame[:] = dict()

    def merge(self, dest, src):
        """
        Given two buffers that contain sum of variances, sum of frames,
        and the number of frames used in each of the partitions, merge the
        partitions and compute the joint sum of variances and sum of frames
        over all frames used

        Parameters
        ----------
        dest
            Partial results that contains sum of variances, sum of frames, and the
            number of frames used over all the frames used

        src
            Partial results that contains sum of variances, sum of frames, and the
            number of frames used over current iteration of partition
        """
        N0 = _validate_n(dest['num_frame'][0])
        N1 = _validate_n(src['num_frame'][0])
        p0 = VariancePart(var=dest['var'][:],
                        sum_im=dest['sum_frame'][:],
                        N=N0)
        p1 = VariancePart(var=src['var'][:],
                        sum_im=src['sum_frame'][:],
                        N=N1)
        compute_merge = merge(p0, p1)

        dest['var'][:] = compute_merge.var
        dest['sum_frame'][:] = compute_merge.sum_im
        for key in src['num_frame'][0]:
            dest['num_frame'][0][key] = compute_merge.N

    def process_tile(self, tile):
        """
        Given a frame, update sum of variances, sum of frames,
        and the number of total frames

        Parameters
        ----------
        tile
            tile of the data
        """

        key = self.meta.slice.discard_nav()

        if key not in self.results.num_frame[0]:
            self.results.num_frame[0][key] = 0

        tile_sum = tile.sum(axis=0)

        p0 = VariancePart(
            var=self.results.var,
            sum_im=self.results.sum_frame,
            N=self.results.num_frame[0][key]
        )
        p1 = VariancePart(
            # We doctor ddof to ensure the sum of variances is divided by one.
            # That way we avoid multiplying by N again for this algorithm
            var=np.var(tile, axis=0, ddof=tile.shape[0]-1),
            sum_im=tile_sum,
            N=tile.shape[0]
        )
        compute_merge = merge(p0, p1)

        self.results.var[:] = compute_merge.var

        self.results.sum_frame[:] = compute_merge.sum_im
        self.results.num_frame[0][key] = compute_merge.N


def consolidate_result(udf_result):
    udf_result = dict(udf_result.items())
    num_frame = _validate_n(udf_result['num_frame'].data[0])

    udf_result['var'] = udf_result['var'].data/num_frame
    udf_result['std'] = np.sqrt(udf_result['var'].data)

    udf_result['mean'] = udf_result['sum_frame'].data/num_frame
    udf_result['num_frame'] = num_frame
    udf_result['sum_frame'] = udf_result['sum_frame'].data
    return udf_result


def run_stddev(ctx, dataset, roi=None):
    """
    Compute sum of variances and sum of pixels from the given dataset

    One-pass algorithm used in this code is taken from the following paper:
    "Numerically Stable Parallel Computation of (Co-) Variance"
    DOI : https://doi.org/10.1145/3221269.3223036

    Parameters
    ----------
    ctx : libertem.api.Context

    dataset : libertem.io.dataset.base.DataSet
        dataset to work on

    Returns
    -------
    pass_results
        A dictionary of narrays that contains sum of variances, sum of pixels,
        and number of frames used to compute the above statistic

    To retrieve statistic, using the following commands:
    variance : pass_results['var']
    standard deviation : pass_results['std']
    sum of pixels : pass_results['sum_frame']
    mean : pass_results['mean']
    number of frames : pass_results['num_frame']
    """
    stddev_udf = StdDevUDF()
    pass_results = ctx.run_udf(dataset=dataset, udf=stddev_udf, roi=roi)

    return consolidate_result(pass_results)
