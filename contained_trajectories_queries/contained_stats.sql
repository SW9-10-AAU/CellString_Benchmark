 -- Contained supercover stats on cardinality of cellstrings at different zoom levels
select contain_super.trajectory_id, cardinality(super_cs.cellstring_z21) as superz21,
       cardinality(contain_super.cellstring_z21) as contain_superz21,
       cardinality(super_cs.cellstring_z17) as superz17,
       cardinality(contain_super.cellstring_z17) as contain_superz17,
       cardinality(super_cs.cellstring_z13) as superz13,
       cardinality(contain_super.cellstring_z13) as contain_superz13
from testcontainment.trajectory_cs as super_cs,
              testcontainment2.trajectory_cs  as contain_super
where super_cs.trajectory_id = contain_super.trajectory_id
order by contain_superz21 desc;

--avg percentage increase in number of cells when using contained supercover vs regular supercover (increase which is expected)
select
    round(avg(
        100.0 * (
            cardinality(contain_super.cellstring_z21)
          - cardinality(super_cs.cellstring_z21)
        )
        / nullif(cardinality(super_cs.cellstring_z21),0)
    ), 4) as pct_increase_z21,

    round(avg(
        100.0 * (
            cardinality(contain_super.cellstring_z17)
          - cardinality(super_cs.cellstring_z17)
        )
        / nullif(cardinality(super_cs.cellstring_z17),0)
    ), 4) as pct_increase_z17,

    round(avg(
        100.0 * (
            cardinality(contain_super.cellstring_z13)
          - cardinality(super_cs.cellstring_z13)
        )
        / nullif(cardinality(super_cs.cellstring_z13),0)
    ), 4) as pct_increase_z13

from testcontainment.trajectory_cs super_cs
join testcontainment2.trajectory_cs contain_super
  on super_cs.trajectory_id = contain_super.trajectory_id;


-- contain - check for any violations of containment (should be zero if all trajectories are fully contained)
SELECT ls.trajectory_id
FROM testcontainment3.trajectory_ls ls
JOIN testcontainment3.trajectory_cs cs
    ON ls.trajectory_id = cs.trajectory_id
WHERE NOT ST_Contains(CST_AsMultiPolygon(cs.cellstring_z21, 21), ls.geom)
  OR NOT ST_Contains(CST_AsMultiPolygon(cs.cellstring_z17, 17), ls.geom)
  OR NOT ST_Contains(CST_AsMultiPolygon(cs.cellstring_z13, 13), ls.geom);


--cover - check for any violations of coverage (should be zero if all trajectories are fully covered)
SELECT ls.trajectory_id
FROM prototype2.trajectory_ls ls
JOIN prototype2.trajectory_contained_supercover_cs cs
    ON ls.trajectory_id = cs.trajectory_id
WHERE ST_Covers(CST_AsMultiPolygon(cs.cellstring_z21, 21), ls.geom) = false;
