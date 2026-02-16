export interface OperatorRef {
  id: number;
  name: string;
}

export type ReserveGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] };

export interface NatureReserveDetail {
  id: string;
  name: string | null;
  area_type: string;
  protect_class: string | null;
  tags: Record<string, unknown>;
  operators: OperatorRef[];
  geometry: ReserveGeometry | null;
  created_at?: string;
  updated_at?: string;
}

export interface NatureReserveListItem {
  id: string;
  name: string | null;
  area_type: string;
}
