import os
import json
import pytest
from requests.auth import HTTPBasicAuth
from unittest.mock import MagicMock, call, patch
import publish_to_cgw_wrapper as cgw_wrapper
from test_publish_to_cgw_wrapper import metadata, content_dir, data_file


@pytest.fixture
def temp_data_file(tmp_path, data_file):
    """Create a temporary data file."""
    data_file_path = tmp_path / "data.json"
    data_file_path.write_text(json.dumps(data_file))
    return data_file_path


@pytest.fixture
def temp_output_file(tmp_path):
    """Create a temporary output file path."""
    return tmp_path / "result.txt"


@patch("publish_to_cgw_wrapper.call_cgw_api")
@patch.dict(os.environ, {"CGW_USERNAME": "username", "CGW_PASSWORD": "password"})
@patch("sys.argv", new_callable=lambda: ["publish_to_cgw_wrapper.py"])
def test_main_creates_files(
    mock_sys_argv, mock_call, temp_data_file, temp_output_file, content_dir, metadata
):
    """Test the main() function where all files are created."""

    test_args = [
        "--cgw_host",
        "https://cgw.com/cgw/rest/admin",
        "--data_file",
        str(temp_data_file),
        "--content_dir",
        str(content_dir),
        "--output_file",
        str(temp_output_file),
    ]
    mock_sys_argv.extend(test_args)

    mock_call.side_effect = [
        MagicMock(
            json=lambda: [
                {"id": 356067, "name": "product_name_1", "productCode": "product_code_1"}
            ]
        ),  # Get products
        MagicMock(json=lambda: [{"id": 4156067, "versionName": "1.1"}]),  # Get version
        MagicMock(json=lambda: []),  # Get existing files
        MagicMock(json=lambda: 4567),  # cosign-linux-amd64.gz (create)
        MagicMock(json=lambda: 4568),  # sha256778877.txt (create)
        MagicMock(json=lambda: 4569),  # cosign (create)
        MagicMock(json=lambda: 4570),  # cosign-checksum.gpg (create)
        MagicMock(json=lambda: 4571),  # gitsign-darwin-amd64.gz (create)
    ]

    cgw_wrapper.main()
    assert temp_output_file.exists()
    final_result_path = temp_output_file.read_text(encoding="utf-8")
    assert final_result_path.endswith("result.json")
    with open(final_result_path) as f:
        result_json = json.load(f)
    assert result_json["no_of_files_processed"] == 5
    assert result_json["no_of_files_created"] == 5
    assert result_json["no_of_files_skipped"] == 0
    assert result_json["metadata"] == metadata


@patch("publish_to_cgw_wrapper.call_cgw_api")
@patch.dict(os.environ, {"CGW_USERNAME": "user", "CGW_PASSWORD": "password"})
@patch("sys.argv", new_callable=lambda: ["publish_to_cgw_wrapper.py"])
def test_main_skips_3_creates_2(
    mock_sys_argv, mock_call, temp_data_file, temp_output_file, content_dir, metadata
):
    """Test for main() when 3 files are skipped and 2 are created."""
    test_args = [
        "--cgw_host",
        "https://cgw.com/cgw/rest/admin",
        "--data_file",
        str(temp_data_file),
        "--content_dir",
        str(content_dir),
        "--output_file",
        str(temp_output_file),
    ]
    mock_sys_argv.extend(test_args)

    mock_call.side_effect = [
        MagicMock(
            json=lambda: [
                {"id": 356067, "name": "product_name_1", "productCode": "product_code_1"}
            ]
        ),  # Get products
        MagicMock(json=lambda: [{"id": 4156067, "versionName": "1.1"}]),  # Get version
        MagicMock(
            json=lambda: [
                {**metadata[0], "id": 4567},  # cosign-linux-amd64.gz (exists)
                {**metadata[1], "id": 4568},  # sha256778877.txt (exists)
                {**metadata[2], "id": 4569},  # cosign (exists)
            ]  # Get existing files
        ),
        MagicMock(json=lambda: 4570),  # sha256778877.txt (create)
        MagicMock(json=lambda: 4571),  # cosign-checksum.gpg (create)
    ]

    cgw_wrapper.main()

    assert temp_output_file.exists()

    final_result_path = temp_output_file.read_text(encoding="utf-8")
    with open(final_result_path) as f:
        result_json = json.load(f)

    assert result_json["no_of_files_processed"] == 5
    assert result_json["no_of_files_created"] == 2
    assert result_json["no_of_files_skipped"] == 3
    assert result_json["metadata"] == metadata


@patch("publish_to_cgw_wrapper.call_cgw_api")
@patch.dict(os.environ, {"CGW_USERNAME": "user", "CGW_PASSWORD": "password"})
@patch("sys.argv", new_callable=lambda: ["publish_to_cgw_wrapper.py"])
def test_main_partial_skip_fail_rollback(
    mock_sys_argv, mock_call, temp_data_file, temp_output_file, content_dir, metadata
):
    """Test the main() where 5 file are tried to be created, 2 are skipped, 1
    is created, 1 fails and 2 are rolled back."""

    test_args = [
        "--cgw_host",
        "https://cgw.com/cgw/rest/admin",
        "--data_file",
        str(temp_data_file),
        "--content_dir",
        str(content_dir),
        "--output_file",
        str(temp_output_file),
    ]
    mock_sys_argv.extend(test_args)

    auth = HTTPBasicAuth("user", "password")

    mock_call.side_effect = [
        MagicMock(
            json=lambda: [
                {"id": 356067, "name": "product_name_1", "productCode": "product_code_1"}
            ]
        ),  # Get products
        MagicMock(json=lambda: [{"id": 4156067, "versionName": "1.1"}]),  # Get version
        MagicMock(
            json=lambda: [
                {**metadata[0], "id": 4571},  # cosign-linux-amd64.gz (exists)
                {**metadata[1], "id": 4572},  # sha256778877.txt (exists)
            ]
        ),
        MagicMock(json=lambda: 4573),  # cosign (create)
        MagicMock(json=lambda: 4574),  # cosign-checksum.gpg (create)
        RuntimeError("File is already present in system"),  # Fail to create
        MagicMock(),  # Delete for file ID 4573
        MagicMock(),  # Delete for file ID 4574
    ]

    with pytest.raises(SystemExit) as exc:
        cgw_wrapper.main()
    assert exc.value.code == 1

    expected_delete_calls = [
        call(
            "https://cgw.com/cgw/rest/admin",
            "DELETE",
            "/products/356067/versions/4156067/files/4573",
            auth,
        ),
        call(
            "https://cgw.com/cgw/rest/admin",
            "DELETE",
            "/products/356067/versions/4156067/files/4574",
            auth,
        ),
    ]
    mock_call.assert_has_calls(expected_delete_calls, any_order=True)
    assert mock_call.call_count == 8
