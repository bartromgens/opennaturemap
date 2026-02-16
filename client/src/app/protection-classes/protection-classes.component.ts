import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { PROTECTION_LEVEL_OPTIONS } from '../map/protection-class';

export interface ProtectionCategoryInfo {
  value: string;
  label: string;
  osmValues: string;
  description: string;
}

const CATEGORY_DESCRIPTIONS: Record<string, { osmValues: string; description: string }> = {
  strict: {
    osmValues: '1a, 1b, 1',
    description:
      'Strict nature reserves (Ia) and wilderness areas (Ib). Set aside for biodiversity and geology; human access strictly controlled. Wilderness: large, largely unmodified areas, no permanent habitation; self-reliant travel only.',
  },
  national_park: {
    osmValues: '2',
    description:
      'Large natural or near-natural areas protecting ecosystems and large-scale processes. Allow compatible recreation, education, and spiritual use. Often tagged as boundary=national_park.',
  },
  habitat_monument: {
    osmValues: '3, 4',
    description:
      'Natural monument or feature (III): protects a specific natural feature (landform, cave, ancient grove); often small with high visitor use. Habitat/species management (IV): protects particular species or habitats; management may include active intervention.',
  },
  landscape_sustainable: {
    osmValues: '5, 6',
    description:
      'Protected landscape/seascape (V): long-term interaction of people and nature has created distinct character; safeguarding that interaction is central. Protected area with sustainable use (VI): conservation together with cultural values and traditional resource management.',
  },
  eu_international: {
    osmValues: '97',
    description:
      'EU/international (continental): e.g. Natura 2000 (SAC, SPA, SCI), Habitats Directive, Birds Directive, Emerald Network. Very common in European data.',
  },
  international_intercontinental: {
    osmValues: '98',
    description:
      'International (intercontinental): e.g. UNESCO Global Geoparks, Biosphere Reserves, Ramsar sites, Barcelona Convention, AEWA. Not used for cross-border national parks (use 2).',
  },
  resource: {
    osmValues: '11–19',
    description:
      'Focus on a single resource or human use; often designated at local level. Examples: water (12), species/fishery/hunting (14, 15, 19), flood retention, protection forest (16).',
  },
  social_cultural: {
    osmValues: '21–29',
    description:
      'Community life (21): religious/sacred, gathering, recreation. Cultural assets (22): historic heritage, monument conservation. Political/indigenous (24): aboriginal/indigenous lands. Other (e.g. 27): publicly accessible outdoor areas by law.',
  },
  other: {
    osmValues: '7, 99 and text values',
    description:
      'Protected by local or regional law (7). Other continental or international not yet classified (99). Country-specific or legal names (e.g. Natuurschoonwet 1928) appear as protect_class in some regions; stored as-is.',
  },
};

@Component({
  selector: 'app-protection-classes',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatIconModule],
  templateUrl: './protection-classes.component.html',
  styleUrl: './protection-classes.component.css',
})
export class ProtectionClassesComponent {
  protected categories: ProtectionCategoryInfo[] = PROTECTION_LEVEL_OPTIONS.map((opt) => ({
    value: opt.value,
    label: opt.label,
    osmValues: CATEGORY_DESCRIPTIONS[opt.value]?.osmValues ?? '—',
    description: CATEGORY_DESCRIPTIONS[opt.value]?.description ?? '',
  }));
}
