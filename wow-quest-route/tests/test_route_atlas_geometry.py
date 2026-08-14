from lib.route_atlas_geometry import (
    bbox_iou,
    cloud_summary,
    compass_direction,
    nearest_point,
    pair_metrics,
    principal_axis,
)


def test_compass_direction_uses_map_y_axis():
    assert compass_direction(0, -5) == "北"
    assert compass_direction(5, 0) == "东"
    assert compass_direction(5, 5) == "东南"
    assert compass_direction(-5, -5) == "西北"


def test_principal_axis_detects_horizontal_cloud():
    axis = principal_axis([[0, 0], [5, 0], [10, 0]])
    assert axis is not None
    assert axis["direction"] == "东西"
    assert axis["axis_strength"] == 1.0


def test_nearest_point_reports_direction():
    row = nearest_point([[10, 10]], [[15, 5], [30, 30]])
    assert row is not None
    assert row["target"] == [15.0, 5.0]
    assert row["direction"] == "东北"


def test_pair_metrics_identical_cloud_is_zero_distance_and_full_bbox_iou():
    points = [[10, 10], [20, 20], [15, 13]]
    metrics = pair_metrics(points, points)
    assert metrics is not None
    assert metrics["minimum_point_distance"] == 0
    assert metrics["symmetric_nn_p50"] == 0
    assert metrics["bbox_iou"] == 1


def test_bbox_iou_for_separate_clouds_is_zero():
    assert bbox_iou([[0, 0], [1, 1]], [[2, 2], [3, 3]]) == 0


def test_cloud_summary_contains_range_and_axis():
    summary = cloud_summary([[0, 0], [10, 0], [20, 0]])
    assert summary is not None
    assert summary["point_count"] == 3
    assert summary["centroid"] == [10.0, 0.0]
    assert summary["bbox"]["width"] == 20
    assert summary["principal_axis"]["direction"] == "东西"
