Feature: Fuzzy Entity Reconciler
  As a data analyst or ops engineer
  I want to upload two lists of entities and run configurable fuzzy comparison
  So that I can identify temporal variants and spatial correlation candidates that were not linked at import time
  And reconcile them with visual feedback and auditable exports

  Background:
    Given the Fuzzy Reconciler service is running locally
    And demo sample data is available via "Load Demo Data"

  @smoke @demo
  Scenario: Load demo data and run default comparison
    Given I am on the ingestion screen
    When I click "Load Demo Data"
    Then both List A and List B are populated with realistic entities
    And schema mapping is auto-detected or pre-filled
    When I accept the defaults and click "Run Fuzzy Comparison"
    Then results appear within a few seconds
    And the summary shows counts for exact_match, temporal_variant, spatial_proximity_candidate, unmatched, etc.
    And the interactive map displays colored markers and connecting lines for matched pairs

  @config @temporal
  Scenario: Detect temporal variant with date tolerance
    Given two versions of the same POI exist in the lists
      | name              | lat     | lon      | analyzed_at   |
      | Cell Site Alpha-7 | 28.1234 | -80.5678 | 2026-03-01T10:00:00Z |
      | Cell Site Alpha-7 | 28.1235 | -80.5679 | 2026-03-18T14:30:00Z |
    And date_tolerance_days is set to 30
    When I run the comparison
    Then the pair is classified as "temporal_variant"
    And the detail view shows date_diff of 17 days and high composite score
    And it is not counted purely as unmatched or simple duplicate

  @geo @spatial
  Scenario: Surface spatial proximity candidate (nearby + similar characteristics)
    Given two records representing the same physical asset but with name drift
      | name                | lat     | lon      | type     | attrs.height_m | attrs.operator |
      | North Tower Array   | 28.5555 | -80.9999 | facility | 45             | Verizon        |
      | Site NT-07          | 28.5568 | -80.9987 | facility | 47             | Verizon        |
    And they are 180 meters apart
    And name_similarity is below threshold but attr_similarity and geo are strong
    When I run with max_geo_distance_m = 300
    Then the pair appears as "spatial_proximity_candidate"
    And the score breakdown clearly shows geo_dist≈180m, name low, attr high
    And the map highlights it in the candidate color (amber/yellow)

  @ui @reconcile
  Scenario: Interactive reconciliation workflow
    Given comparison results are displayed (table + map)
    When I filter the table to "spatial_proximity_candidate"
    And I click a row to inspect details
    Then the side panel shows side-by-side fields, score gauges, and provenance
    When I click "Confirm Match & Merge" and add a short note
    Then the classification badge updates to "confirmed_match"
    And the item is added to the working reconciled master list
    And the change appears in the decision audit log with timestamp
    When I export "Reconciled Master (CSV)"
    Then the file contains the merged record with _match_classification, _composite_score, _notes, and source provenance columns

  @api @integration
  Scenario: API compare endpoint returns structured classified results
    Given I have two small normalized entity lists in JSON
    When I POST them with a config payload to /compare
    Then I receive 200 with summary counts and a matches array
    And each match entry includes composite_score, individual scores, classification, geo_distance_m, date_diff_days, and full item snapshots
    And classifications follow the documented rules (temporal_variant when dates differ within tolerance and scores high, etc.)

  @performance @mvp
  Scenario: Handles moderate sized lists acceptably
    Given List A and List B each contain 1500 realistic entities
    When I run comparison with default blocking and scoring
    Then results are returned in under 15 seconds on standard developer hardware
    And memory usage remains reasonable
    And the UI remains responsive during processing (or shows clear progress)

  @export @audit
  Scenario: Full auditability of automated + manual decisions
    Given a session with both automated classifications and several manual confirm/reject/merge actions
    When I export the full results package (JSON or ZIP)
    Then every pair carries its final classification, score vector, and the config/thresholds used at time of run
    And manual decisions include actor (local user), timestamp, rationale, and before/after values
    And the reconciled master export is usable directly for downstream import into a master database or GIS tool

# Additional scenarios can be added for: error handling on bad uploads, preset loading/saving, ambiguous multi-candidate cases, cluster creation for >2 items, keyboard navigation, dark mode, large file streaming, etc.
# Map-specific interactions (layer toggle syncs table filter, click marker highlights row and opens detail) should also be covered in UI tests.