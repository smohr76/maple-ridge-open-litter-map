## Taxonomy Crosswalk Engine & Dual-Schema Contract
1. System Context & Architectural RationaleOpenLitterMap (OLM) exposes a global data dictionary focused on granular object tagging (Category-Litter-Object schema). However, regional municipal bodies—such as Metro Vancouver, the City of Maple Ridge, and environmental stewardship groups like the Alouette River Mentorship Society (ARMS)—evaluate waste through specific policy lenses:Single-Use Plastics & Item Reduction Bylaws (e.g., City of Vancouver Bylaw No. 12566, Metro Vancouver Model Bylaws).Solid Waste Composition Audits (Paper/Cardboard Organics Diversion).Hazardous & Biohazardous Risk Mitigation (Cigarette butts as dry-season fire hazards; vapes, batteries, and pet waste as toxics/contaminants).Bylaw Enforcement & Dumping Remediation (City of Maple Ridge Bylaw No. 5115-1994).The Taxonomy Crosswalk Engine is a build-time ETL module that translates raw OLM records into a 4-pillar localized audit schema. Executing this crosswalk statically on GitHub Actions eliminates runtime database costs ($0.00 infrastructure) while producing policy-grade spatial data for local stakeholders.2. Upstream vs. Downstream GeoJSON Schema Contract2.1 Upstream Source Payload (Raw OpenLitterMap API Feature)Raw OLM features include nested tag arrays, brand names, and sub-types that introduce field friction and redundancy. Primary physical items are identified by the presence of a non-null clo_id.JSON{
  "id": 552998,
  "lat": 49.209568,
  "lon": -122.561569,
  "created_at": "2026-09-18T14:30:00Z",
  "summary": {
    "tags": [
      {
        "clo_id": 102,
        "category": "smoking",
        "item": "butts",
        "quantity": 2,
        "materials": [],
        "brands": []
      },
      {
        "clo_id": 45,
        "category": "softdrinks",
        "item": "cup",
        "quantity": 1,
        "materials": ["plastic"],
        "brands": ["McDonald's"]
      }
    ]
  }
}
2.2 Downstream Target Payload (public/data/litter.geojson)The target schema strips brands and sub-types to reduce file size by ~55%. It aggregates quantities into Metro Vancouver categories and computes an integer categoryMask for 60 FPS WebGL filtering in MapLibre GL JS.JSON{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-122.561569, 49.209568]
      },
      "properties": {
        "id": 552998,
        "datetime": "2026-09-18T14:30:00Z",
        "totalItems": 3,
        "categoryMask": 5,
        "groups": ["single_use_plastics", "hazardous_waste"],
        "metroVanCounts": {
          "single_use_plastics": 1,
          "paper_composites": 0,
          "hazardous_waste": 2,
          "other_recyclables": 0
        },
        "items": [
          {
            "metroCategory": "hazardous_waste",
            "olmObject": "butts",
            "quantity": 2
          },
          {
            "metroCategory": "single_use_plastics",
            "olmObject": "cup",
            "quantity": 1
          }
        ]
      }
    }
  ]
}
3. The 4-Pillar Taxonomy Crosswalk MatrixThe table below defines how incoming OLM tags are parsed during build time.Target Metro Van Category KeyMask Bit & IntegerSource OLM Category KeysSource OLM Object Keys (item)Source OLM Material KeysRegional Regulatory Alignmentsingle_use_plasticsBit 0 (mask: 1)softdrinks, food, marinecup, container, plastic_bag, straw, wrapper, crisp_packet, cutlery, styrofoam, bottleplastic, polymer, polystyrene, foamMetro Van Single-Use Item Strategy & City of Vancouver Bylaw No. 12566.paper_compositesBit 1 (mask: 2)coffee, civicsleeve, napkins, carton, tissue, poster, paper_bagpaper, cardboardMetro Van Solid Waste Management Plan (Paper/Organics Diversion).hazardous_waste (Toxic)Bit 2 (mask: 4)smoking, pets, medical, sanitary, electronicsbutts, vape, lighters, dogshit, dogshit_in_bag, bandage, gloves, batteryDerived by Category & ObjectCity of Maple Ridge Parks Protocols (Biohazard, Toxic, and Fire Hazard Risk).other_recyclablesBit 3 (mask: 8)industrial, vehicles, dumping, alcoholcan, bottle, broken_glass, metal, construction, pipe, car_partaluminium, metal, ceramic, woodCity of Maple Ridge Bylaw No. 5115-1994 (Blue Box & Dumping).4. Bitmask Filtering Mathematics (categoryMask)To eliminate expensive string parsing on the browser main thread, each spatial feature is assigned an integer bitmask derived from active waste streams:$$\text{categoryMask} = \sum_{i \in \text{active streams}} 2^i$$single_use_plastics = Bit 0 ($2^0 = 1$)paper_composites = Bit 1 ($2^1 = 2$)hazardous_waste = Bit 2 ($2^2 = 4$)other_recyclables = Bit 3 ($2^3 = 8$)MapLibre GL JS Client IntegrationIn the frontend dashboard, toggling visual layers uses zero-overhead WebGL bitwise evaluation:JavaScript// MapLibre expression: Filter points containing Hazardous/Toxic waste (Bit 2 / Value 4)
map.setFilter('litter-layer', [
  '!=',
  ['bit-and', ['get', 'categoryMask'], 4],
  0
]);
