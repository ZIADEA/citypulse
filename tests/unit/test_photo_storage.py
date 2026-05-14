# Arrange / Act / Assert — stockage photos (sans Qt)
import pytest


def test_save_user_photo_copies(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.utils.photo_storage.project_root", lambda: str(tmp_path)
    )
    src = tmp_path / "shot.png"
    src.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    from app.utils.photo_storage import save_user_photo

    rel = save_user_photo(str(src), "veh", 42)
    assert rel == "data/photos/veh_42_shot.png"
    dest = tmp_path / "data" / "photos" / "veh_42_shot.png"
    assert dest.is_file()
    assert dest.read_bytes() == src.read_bytes()


def test_finalize_keeps_http():
    from app.utils.photo_storage import finalize_stored_path

    assert finalize_stored_path(" https://x/y.jpg ", "d", 1).startswith("https://")


def test_finalize_existing_managed_relative(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.utils.photo_storage.project_root", lambda: str(tmp_path)
    )
    (tmp_path / "data" / "photos").mkdir(parents=True)
    f = tmp_path / "data" / "photos" / "d_1_a.png"
    f.write_bytes(b"x")

    from app.utils.photo_storage import finalize_stored_path

    assert finalize_stored_path("data/photos/d_1_a.png", "d", 99) == "data/photos/d_1_a.png"
