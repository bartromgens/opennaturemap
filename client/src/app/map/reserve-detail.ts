export interface NatureReserveDetail {
  id: string;
  name: string | null;
  area_type: string;
  tags: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}
