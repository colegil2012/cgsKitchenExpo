/**
 * Mirrors the cgsKitchen OrderView contract returned by GET /api/orders/active.
 * Money is integer cents on the wire; format only at the edges.
 */
export interface OrderModifier {
  label: string;
  priceDeltaCents?: number;
}

/**
 * Modifiers on the wire. The structured backend field is an array (label
 * strings, or {label, priceDeltaCents} objects). `string` and `null` are
 * tolerated for legacy/flattened orders so old tickets still render.
 */
export type Modifiers = string[] | OrderModifier[] | string | null;

export interface OrderItemView {
  menuItemId: string;
  name: string;
  quantity: number;
  unitPriceCents: number;
  modifiers?: Modifiers;
}

export interface OrderView {
  id: string;
  status: string; // PAID | IN_KITCHEN | READY | (terminal states never appear in /active)
  fulfillment: string;
  totalCents: number;
  modifiers?: Modifiers;
  createdAt: string;
  updatedAt: string;
  items: OrderItemView[];
}

/** The three columns this board renders, in flow order. */
export type BoardColumn = 'PAID' | 'IN_KITCHEN' | 'READY';

export const BOARD_COLUMNS: BoardColumn[] = ['PAID', 'IN_KITCHEN', 'READY'];

export const COLUMN_LABEL: Record<BoardColumn, string> = {
  PAID: 'Paid',
  IN_KITCHEN: 'In Kitchen',
  READY: 'Ready',
};