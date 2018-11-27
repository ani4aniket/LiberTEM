import * as React from "react";
import { connect, Dispatch } from "react-redux";
import { FixedSizeList as List } from 'react-window';
import { Button, Header, Segment } from "semantic-ui-react";
import { DirectoryListingDetails } from "../../messages";
import { RootReducer } from "../../store";
import * as browserActions from '../actions';
import FileEntry from "./FileEntry";
import FolderEntry from "./FolderEntry";
import RecentFiles from "./RecentFiles";

const mapStateToProps = (state: RootReducer) => {
    const { browser } = state;
    return {
        files: browser.files,
        dirs: browser.dirs,
        path: browser.path,
    };
}

const mapDispatchToProps = (dispatch: Dispatch) => {
    return {
        cancel: () => dispatch(browserActions.Actions.cancel()),
    };
}

type MergedProps = ReturnType<typeof mapStateToProps> & ReturnType<typeof mapDispatchToProps>;

interface EntryFnArgs {
    index: number,
    style: object
}
type EntryFn = (arg: EntryFnArgs) => void

const listRef = React.createRef<List>();

const scrollToTop = () => {
    if (listRef.current === null) {
        return;
    }
    listRef.current.scrollToItem(0);
}

function sortByKey<T extends object>(array: T[], getKey: (item: T) => any) {
    return array.sort((a, b) => {
        const x = getKey(a);
        const y = getKey(b);
        return ((x < y) ? -1 : ((x > y) ? 1 : 0));
    });
}

const FileBrowser: React.SFC<MergedProps> = ({ files, dirs, path, cancel }) => {
    const getSortKey = (item: DirectoryListingDetails) => item.name.toLowerCase();
    const dirEntries = sortByKey(dirs, getSortKey).map((dir) => (style: object) => <FolderEntry style={style} onChange={scrollToTop} path={path} details={dir} />);
    const fileEntries = sortByKey(files, getSortKey).map((f) => ((style: object) => <FileEntry style={style} path={path} details={f} />));
    const entries = dirEntries.concat(fileEntries);
    const entryFn: EntryFn = ({ index, style }) => {
        return entries[index](style)
    };

    return (
        <Segment.Group>
            <Segment.Group horizontal={true}>
                <Segment>
                    <Header as="h2">Open dataset</Header>
                </Segment>
                <Segment style={{ flexShrink: 1, flexGrow: 0 }}>
                    <RecentFiles />
                </Segment>
            </Segment.Group>
            <Segment>
                <p>Path: {path}</p>
                <List ref={listRef} height={300} width="100%" itemCount={entries.length} itemSize={35}>
                    {entryFn}
                </List>
            </Segment>
            <Segment>
                <Button onClick={cancel}>Cancel</Button>
            </Segment>
        </Segment.Group>
    );
}

export default connect(mapStateToProps, mapDispatchToProps)(FileBrowser);