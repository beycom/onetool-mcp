import { useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import type { TableMessage } from "../types";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

interface TableRowProps {
  msg: TableMessage;
}

export function TableRow({ msg }: TableRowProps) {
  const { rows, columns: explicitColumns } = msg;
  const [sorting, setSorting] = useState<SortingState>([]);

  const columnKeys = useMemo(() => {
    if (explicitColumns && explicitColumns.length > 0) return explicitColumns;
    if (rows.length === 0) return [];
    return Object.keys(rows[0]);
  }, [rows, explicitColumns]);

  const columnHelper = createColumnHelper<Record<string, unknown>>();

  const tableColumns = useMemo(
    () =>
      columnKeys.map((key) =>
        columnHelper.accessor((row) => row[key], {
          id: key,
          header: key,
          cell: (info) => {
            const v = info.getValue();
            if (v === null || v === undefined) return "";
            if (typeof v === "object") return JSON.stringify(v);
            return String(v);
          },
        })
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [columnKeys]
  );

  const table = useReactTable({
    data: rows,
    columns: tableColumns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (rows.length === 0) {
    return (
      <div className="text-xs text-gray-400 italic">Empty table</div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm border-collapse">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  onClick={header.column.getToggleSortingHandler()}
                  className="border border-gray-200 dark:border-gray-700 px-3 py-1.5 bg-gray-50 dark:bg-gray-800 font-semibold text-left cursor-pointer select-none whitespace-nowrap"
                >
                  <span className="flex items-center gap-1">
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext()
                    )}
                    {header.column.getIsSorted() === "asc" ? (
                      <ChevronUp size={12} />
                    ) : header.column.getIsSorted() === "desc" ? (
                      <ChevronDown size={12} />
                    ) : (
                      <ChevronsUpDown size={12} className="text-gray-400" />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="hover:bg-gray-50 dark:hover:bg-gray-800/50"
            >
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  className="border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-xs font-mono"
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
