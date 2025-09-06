import pytest

from utils.routes import (
    container_url,
    drawer_url,
    part_url,
    rebrickable_part_color_url,
    rebrickable_part_url,
    rebrickable_set_url,
    set_url,
)

pytestmark = pytest.mark.unit


class TestLocalUrlBuilders:
    @pytest.mark.parametrize(
        "inp,expected",
        [
            (7, "/drawers/7"),
            ("D-042", "/drawers/D-042"),
            ("space here", "/drawers/space%20here"),
            ("weird/slug", "/drawers/weird%2Fslug"),
        ],
    )
    def test_drawer_url(self, inp, expected):
        assert drawer_url(inp) == expected

    @pytest.mark.parametrize(
        "inp,expected",
        [
            (9, "/containers/9"),
            ("C-99", "/containers/C-99"),
            ("name with spaces", "/containers/name%20with%20spaces"),
            ("weird/slug", "/containers/weird%2Fslug"),
        ],
    )
    def test_container_url(self, inp, expected):
        assert container_url(inp) == expected

    @pytest.mark.parametrize(
        "inp,expected",
        [
            (3023, "/parts/3023"),
            ("3023", "/parts/3023"),
            ("tile 1x2", "/parts/tile%201x2"),
            ("3023/alt", "/parts/3023%2Falt"),
        ],
    )
    def test_part_url(self, inp, expected):
        assert part_url(inp) == expected

    @pytest.mark.parametrize(
        "inp,expected",
        [
            ("75192", "/sets/75192"),
            ("set with space", "/sets/set%20with%20space"),
            ("2024/01", "/sets/2024%2F01"),
        ],
    )
    def test_set_url(self, inp, expected):
        assert set_url(inp) == expected


class TestRebrickableUrlBuilders:
    @pytest.mark.parametrize(
        "design_id,expected",
        [
            (3023, "https://rebrickable.com/parts/3023/"),
            ("3023", "https://rebrickable.com/parts/3023/"),
            ("tile 1x2", "https://rebrickable.com/parts/tile%201x2/"),
        ],
    )
    def test_rebrickable_part_url(self, design_id, expected):
        assert rebrickable_part_url(design_id) == expected

    @pytest.mark.parametrize(
        "design_id,color_id,expected",
        [
            (3023, 86, "https://rebrickable.com/parts/3023/86/"),
            ("3023", "86", "https://rebrickable.com/parts/3023/86/"),
            ("3023", None, "https://rebrickable.com/parts/3023/"),
            ("tile 1x2", "86", "https://rebrickable.com/parts/tile%201x2/86/"),
        ],
    )
    def test_rebrickable_part_color_url(self, design_id, color_id, expected):
        assert rebrickable_part_color_url(design_id, color_id) == expected

    @pytest.mark.parametrize(
        "set_num,expected",
        [
            ("75192", "https://rebrickable.com/sets/75192/"),
            ("set with space", "https://rebrickable.com/sets/set%20with%20space/"),
        ],
    )
    def test_rebrickable_set_url(self, set_num, expected):
        assert rebrickable_set_url(set_num) == expected
