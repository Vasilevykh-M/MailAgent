import { DataListItem } from './DataListItem'
import { DataListRoot } from './DataListRoot'

export const DataList = Object.assign(DataListRoot, {
  Item: DataListItem,
})

export type { DataListItemProps } from './DataListItem'
