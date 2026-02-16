/** Protection level categories from docs/protect_class.md */

export const PROTECTION_LEVEL_OPTIONS: { value: string; label: string }[] = [
  { value: 'strict', label: 'Strict / wilderness' },
  { value: 'national_park', label: 'National park' },
  { value: 'habitat_monument', label: 'Habitat / species / monument' },
  { value: 'landscape_sustainable', label: 'Landscape / sustainable use' },
  { value: 'eu_international', label: 'EU/international (continental)' },
  { value: 'international_intercontinental', label: 'International (intercontinental)' },
  { value: 'resource', label: 'Resource protection' },
  { value: 'social_cultural', label: 'Social / cultural protection' },
  { value: 'other', label: 'Other / local / unclassified' },
];

export function protectionLevelFromProtectClass(
  protectClass: string | null | undefined,
): string | null {
  if (protectClass == null || protectClass === '') return null;
  const v = String(protectClass).trim().toLowerCase();
  if (v === '1a' || v === '1b' || v === '1') return 'strict';
  if (v === '2') return 'national_park';
  if (v === '3' || v === '4') return 'habitat_monument';
  if (v === '5' || v === '6') return 'landscape_sustainable';
  if (v === '97') return 'eu_international';
  if (v === '98') return 'international_intercontinental';
  const n = Number(v);
  if (!Number.isNaN(n) && Number.isInteger(n)) {
    if (n >= 11 && n <= 19) return 'resource';
    if (n >= 21 && n <= 29) return 'social_cultural';
  }
  if (v === '7' || v === '99') return 'other';
  return 'other';
}

export function getProtectionLevelLabel(protectClass: string | null | undefined): string | null {
  const value = protectionLevelFromProtectClass(protectClass);
  if (value == null) return null;
  const opt = PROTECTION_LEVEL_OPTIONS.find((o) => o.value === value);
  return opt?.label ?? null;
}
