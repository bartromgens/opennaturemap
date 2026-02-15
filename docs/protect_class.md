# OSM protect_class – Protection level reference

In OpenStreetMap, protected areas use `boundary=protected_area` (or `boundary=national_park`) together with **`protect_class`** to describe the type and level of protection. The values are stored in our `NatureReserve.protect_class` field, sourced from the OSM tag `protect_class`.

**Sources:** [OSM Tag:boundary=protected_area](https://wiki.openstreetmap.org/wiki/Tag:boundary%3Dprotected_area), [OSM Key:protect_class](https://wiki.openstreetmap.org/wiki/Key:protect_class), [OSM Template:IUCN_Categories](https://wiki.openstreetmap.org/wiki/Template:IUCN_Categories).

---

## Overview

`protect_class` is split into four ranges:

| Range   | Meaning |
|--------|---------|
| **1a, 1b, 1–6** | Nature conservation, aligned with IUCN protected area categories (international standard). |
| **7, 97–99**    | Other nature conservation (EU/international schemes, or local; OSM-specific numbering). |
| **11–19**       | Resource protection (water, species, land; single-resource focus). |
| **21–29**       | Social/cultural protection (community, heritage, recreation, etc.). |

Values **1** and **7–99** are not from an external standard; they were defined for OSM. Country-specific or legal names (e.g. `Natuurschoonwet 1928`) also appear as `protect_class` in some regions.

---

## IUCN-based nature protection (1a, 1b, 1–6)

These correspond to [IUCN protected area management categories](https://en.wikipedia.org/wiki/IUCN_protected_area_categories), recognised by the UN and Convention on Biological Diversity.

| protect_class | IUCN | Description |
|---------------|------|-------------|
| **1a** or **1** | Ia | **Strict nature reserve** – Set aside for biodiversity and possibly geology; human access and use strictly controlled; used as reference for science and monitoring. |
| **1b** or **1** | Ib | **Wilderness area** – Large, largely unmodified areas, no permanent habitation; managed to preserve natural condition; self-reliant travel (e.g. on foot) only. |
| **2** | II | **National park** – Large natural/near-natural areas protecting ecosystems and large-scale processes; allow compatible recreation, education, and spiritual use. Often tagged as `boundary=national_park` instead. |
| **3** | III | **Natural monument or feature** – Protects a specific natural feature (landform, cave, ancient grove, etc.); often small and with high visitor use. |
| **4** | IV | **Habitat/species management area** – Protects particular species or habitats; management may include active intervention. |
| **5** | V | **Protected landscape/seascape** – Areas where long-term interaction of people and nature has created distinct character with ecological, cultural, and scenic value; safeguarding that interaction is central. |
| **6** | VI | **Protected area with sustainable use** – Ecosystem and habitat conservation together with cultural values and traditional resource management; part of area under sustainable, low-level use compatible with conservation. |

---

## Other nature conservation (7, 97–99)

| protect_class | Description |
|---------------|-------------|
| **7** | Protected by local or regional law: e.g. single species, vegetation type, or geological site. |
| **97** | **EU/international (continental)** – e.g. **Natura 2000** (SAC, SPA, SCI), Habitats Directive, Birds Directive, Emerald Network. Very common in European data. |
| **98** | **International (intercontinental)** – e.g. UNESCO Global Geoparks, Biosphere Reserves, Ramsar sites, Barcelona Convention, AEWA. Not used for cross-border national parks (use 2). |
| **99** | Other continental or international, not yet classified. |

---

## Resource protection (11–19)

Focus on a single resource or human use; often designated at local level.

| protect_class | Focus (examples) |
|---------------|------------------|
| **11–19** | Water (12), species/fishery/hunting (14, 15, 19), location/condition (e.g. flood retention, protection forest) (16). Some values are rarely used. |

---

## Social / cultural protection (21–29)

| protect_class | Description |
|---------------|-------------|
| **21** | Community life: religious/sacred, gathering, recreation (e.g. some US state parks). |
| **22** | Cultural assets: historic heritage, monument conservation, architecture, historic districts. |
| **24** | Political/indigenous: aboriginal/indigenous lands (often tagged as `boundary=aboriginal_lands` instead). |
| **27** | e.g. Norwegian “Friluftsområde” (publicly accessible outdoor areas by law). |

---

## Country- and law-specific values

`protect_class` can also be a **text value** from national law or local practice, for example:

- **Natuurschoonwet 1928** (Netherlands) – nature reserves under the 1928 “Nature Beauty Act”.
- **Natuurschoonwet 1928, opengesteld** / **niet opengesteld** – open vs not open to the public.
- Other country-specific codes (e.g. Poland “Użytek ekologiczny” has been mapped to numeric or other values).

These are stored as-is in `protect_class`; interpretation depends on the country/region.

---

## Summary for map/UI

- **Strictest nature protection:** 1a, 1b, 1 → then 2 (national park) → 3, 4 → 5, 6.
- **EU/international overlay:** 97 (e.g. Natura 2000), 98 (e.g. Ramsar, UNESCO).
- **Local / other:** 7, 99 and text values (e.g. Natuurschoonwet 1928).

For styling or filtering by “protection level”, a simple grouping is:

1. **Strict / wilderness:** 1a, 1b, 1  
2. **National park:** 2  
3. **Habitat / species / monument:** 3, 4  
4. **Landscape / sustainable use:** 5, 6  
5. **EU/international (continental):** 97  
6. **International (intercontinental):** 98  
7. **Resource protection:** 11–19  
8. **Social / cultural protection:** 21–29  
9. **Other / local / unclassified:** 7, 99 and any text value  
