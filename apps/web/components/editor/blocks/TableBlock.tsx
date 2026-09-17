import type { Block, TableData } from "@html-office/contracts";

export function DataTable({ table }: { table: TableData }) {
  return (
    <div className="table-block">
      <table>
        <thead>
          <tr>
            {table.columns.map((column) => (
              <th key={column} scope="col">{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{String(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TableBlock({ block }: { block: Extract<Block, { kind: "table" }> }) {
  return <DataTable table={block.table} />;
}
