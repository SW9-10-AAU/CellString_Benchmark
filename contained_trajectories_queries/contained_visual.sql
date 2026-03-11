-- ==========================================================
-- Visualize LineString containment with Supercover CellString
-- ==========================================================
SELECT
    ls.trajectory_id,
    ls.mmsi,
    ls.ts_start,
    ls.ts_end,
    cs.ts_start,
    cs.ts_end,
    ls.geom AS original_trajectory,

    -- Decoded CellString as polygons at different zoom levels
    --CST_AsMultiPolygon(cs.cellstring_z13, 13) AS cells_z13,
    --CST_AsMultiPolygon(cs.cellstring_z17, 17) AS cells_z17,
    CST_AsMultiPolygon(cs.cellstring_z21, 21) AS cells_z21,

    -- Containment check (TRUE = contained, FALSE = violation)
    ST_Contains(CST_AsMultiPolygon(cs.cellstring_z13, 13), ls.geom) AS z13_contained,
    ST_Contains(CST_AsMultiPolygon(cs.cellstring_z17, 17), ls.geom) AS z17_contained,
    ST_Contains(CST_AsMultiPolygon(cs.cellstring_z21, 21), ls.geom) AS z21_contained,

    -- Parts of trajectory NOT covered (for visualization of violations)
    ST_Difference(ls.geom, CST_AsMultiPolygon(cs.cellstring_z13, 13)) AS z13_uncovered,
    ST_Difference(ls.geom, CST_AsMultiPolygon(cs.cellstring_z17, 17)) AS z17_uncovered,
    ST_Difference(ls.geom, CST_AsMultiPolygon(cs.cellstring_z21, 21)) AS z21_uncovered

FROM testcontainment3.trajectory_ls ls
JOIN testcontainment3.trajectory_cs cs
    ON ls.trajectory_id = cs.trajectory_id
WHERE ls.trajectory_id = 5

UNION ALL

SELECT
    ls.trajectory_id,
    ls.mmsi,
    ls.ts_start,
    ls.ts_end,
    cs.ts_start,
    cs.ts_end,
    ls.geom AS original_trajectory,

    -- Decoded CellString as polygons at different zoom levels
    --CST_AsMultiPolygon(cs.cellstring_z13, 13) AS cells_z13,
    --CST_AsMultiPolygon(cs.cellstring_z17, 17) AS cells_z17,
    CST_AsMultiPolygon(cs.cellstring_z21, 21) AS cells_z21,

    -- Containment check (TRUE = contained, FALSE = violation)
    ST_Contains(CST_AsMultiPolygon(cs.cellstring_z13, 13), ls.geom) AS z13_contained,
    ST_Contains(CST_AsMultiPolygon(cs.cellstring_z17, 17), ls.geom) AS z17_contained,
    ST_Contains(CST_AsMultiPolygon(cs.cellstring_z21, 21), ls.geom) AS z21_contained,

    -- Parts of trajectory NOT covered (for visualization of violations)
    ST_Difference(ls.geom, CST_AsMultiPolygon(cs.cellstring_z13, 13)) AS z13_uncovered,
    ST_Difference(ls.geom, CST_AsMultiPolygon(cs.cellstring_z17, 17)) AS z17_uncovered,
    ST_Difference(ls.geom, CST_AsMultiPolygon(cs.cellstring_z21, 21)) AS z21_uncovered

FROM testcontainment2.trajectory_ls ls
JOIN testcontainment2.trajectory_cs cs
    ON ls.trajectory_id = cs.trajectory_id
WHERE ls.trajectory_id = 10;

--
SELECT cs.trajectory_id
FROM prototype2.trajectory_cs cs
JOIN prototype2.trajectory_contained_supercover_cs cscover
  ON cs.trajectory_id = cscover.trajectory_id
WHERE cs.ts_start IS DISTINCT FROM cscover.ts_start
   OR cs.ts_end   IS DISTINCT FROM cscover.ts_end;


-- visualize the difference in cell coverage between regular supercover and contained supercover for a specific trajectory
WITH polygons AS (
    SELECT
        ls.trajectory_id,
        ls.mmsi,
        ls.geom AS original_trajectory,
        CST_AsMultiPolygon(cs.cellstring_z21, 21) AS cells_z21,
        CST_AsMultiPolygon(cs_noncontained.cellstring_z21, 21) AS noncontained_cells_z21
    FROM testcontainment.trajectory_ls ls
    JOIN testcontainment.trajectory_cs cs
        ON ls.trajectory_id = cs.trajectory_id
    JOIN testcontainment2.trajectory_cs cs_noncontained
        ON ls.trajectory_id = cs_noncontained.trajectory_id
    WHERE ls.trajectory_id = 10
)

SELECT trajectory_id, mmsi, 'contained_supercover' AS type, cells_z21 AS geom
FROM polygons

UNION ALL

SELECT trajectory_id, mmsi, 'regular_supercover' AS type, noncontained_cells_z21 AS geom
FROM polygons

UNION ALL

SELECT trajectory_id, mmsi, 'original_traj' AS type, original_trajectory AS geom
FROM polygons
