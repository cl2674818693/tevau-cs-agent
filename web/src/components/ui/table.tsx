import * as React from "react";

import { cn } from "../../lib/utils";

/** 横向滚动容器：窄屏(H5)宽表左右滑动，不撑破布局。包住 <Table> 使用。 */
export const TableScroll = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("-mx-page overflow-x-auto px-page", className)} {...p} />
);

export const Table = ({ className, ...p }: React.TableHTMLAttributes<HTMLTableElement>) => (
  <table className={cn("w-full text-body3", className)} {...p} />
);
export const THead = ({ className, ...p }: React.HTMLAttributes<HTMLTableSectionElement>) => (
  <thead className={cn("text-left text-ink-secondary", className)} {...p} />
);
export const TBody = (p: React.HTMLAttributes<HTMLTableSectionElement>) => <tbody {...p} />;
export const Tr = ({ className, ...p }: React.HTMLAttributes<HTMLTableRowElement>) => (
  <tr className={cn("border-t border-line text-ink-primary", className)} {...p} />
);
export const Th = ({ className, ...p }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
  <th className={cn("py-2 font-normal", className)} {...p} />
);
export const Td = ({ className, ...p }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
  <td className={cn("py-2", className)} {...p} />
);
