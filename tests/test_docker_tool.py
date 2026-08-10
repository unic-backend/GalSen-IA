"""
Tests for the Docker tool.
"""

from unittest.mock import MagicMock

import pytest

from src.tools.docker.tool import DockerTool


@pytest.fixture
def docker_tool():
    """Return a DockerTool instance with default configuration."""
    return DockerTool()


def test_docker_tool_initialization(docker_tool):
    """Test that the tool initializes."""
    assert docker_tool is not None


def test_docker_tool_available_operations(docker_tool):
    """Test that the available operations are returned correctly."""
    assert set(docker_tool.available_operations()) == {
        "list_containers",
        "run_container",
        "stop_container",
        "remove_container",
    }


def test_docker_tool_list_containers_success(docker_tool):
    """Test listing containers returns a list of container dicts."""
    mock_client = MagicMock()
    mock_container1 = MagicMock()
    mock_container1.id = "id1"
    mock_container1.name = "container1"
    mock_container1.status = "running"
    mock_container1.image.tags = ["image1:latest"]
    mock_container1.ports = {}

    mock_container2 = MagicMock()
    mock_container2.id = "id2"
    mock_container2.name = "container2"
    mock_container2.status = "exited"
    mock_container2.image.tags = ["image2:latest"]
    mock_container2.ports = {"80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]}

    mock_client.containers.list.return_value = [mock_container1, mock_container2]

    # Manually set the client on the instance (bypassing __init__)
    docker_tool._client = mock_client

    result = docker_tool.execute("list_containers", all=False)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["id"] == "id1"
    assert result[0]["name"] == "container1"
    assert result[0]["status"] == "running"
    assert result[0]["image"] == "image1:latest"
    assert result[1]["id"] == "id2"
    assert result[1]["name"] == "container2"
    assert result[1]["status"] == "exited"
    assert result[1]["image"] == "image2:latest"
    mock_client.containers.list.assert_called_once_with(all=False)


def test_docker_tool_list_containers_docker_unavailable(docker_tool):
    """Test that listing containers raises RuntimeError when Docker is unavailable."""
    # Simulate Docker not being available
    docker_tool._client = None

    with pytest.raises(RuntimeError, match="Le client Docker n'est pas disponible"):
        docker_tool.execute("list_containers")


def test_docker_tool_list_containers_error(docker_tool):
    """Test that listing containers with an error raises RuntimeError."""
    mock_client = MagicMock()
    mock_client.containers.list.side_effect = Exception("Docker error")
    docker_tool._client = mock_client

    with pytest.raises(RuntimeError, match="Échec de la liste des conteneurs"):
        docker_tool.execute("list_containers")


def test_docker_tool_run_container_success(docker_tool):
    """Test running a container returns success with container ID."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "container_id_123"
    mock_container.name = "mycontainer"
    mock_client.containers.run.return_value = mock_container

    docker_tool._client = mock_client

    result = docker_tool.execute(
        "run_container", image="hello-world", command="echo hello", detach=True
    )

    assert result["status"] == "success"
    assert "conteneur" in result["message"].lower()
    assert "hello-world" in result["message"]
    assert result["container_id"] == "container_id_123"
    assert result["container_name"] == "mycontainer"
    mock_client.containers.run.assert_called_once_with(
        "hello-world", command="echo hello", detach=True
    )


def test_docker_tool_run_container_error(docker_tool):
    """Test that running a container with an error raises RuntimeError."""
    mock_client = MagicMock()
    mock_client.containers.run.side_effect = Exception("Docker error")
    docker_tool._client = mock_client

    with pytest.raises(RuntimeError, match="Échec de l'exécution du conteneur"):
        docker_tool.execute("run_container", image="hello-world")


def test_docker_tool_stop_container_success(docker_tool):
    """Test stopping a container returns success."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container

    docker_tool._client = mock_client

    result = docker_tool.execute("stop_container", container_id="container123")

    assert result["status"] == "success"
    assert "arrêté" in result["message"].lower()
    assert "container123" in result["message"]
    mock_client.containers.get.assert_called_once_with("container123")
    mock_container.stop.assert_called_once()


def test_docker_tool_stop_container_error(docker_tool):
    """Test that stopping a container with an error raises RuntimeError."""
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = Exception("Docker error")
    docker_tool._client = mock_client

    with pytest.raises(RuntimeError, match="Échec de l'arrêt du conteneur"):
        docker_tool.execute("stop_container", container_id="container123")


def test_docker_tool_remove_container_success(docker_tool):
    """Test removing a container returns success."""
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container

    docker_tool._client = mock_client

    result = docker_tool.execute(
        "remove_container", container_id="container123", force=True
    )

    assert result["status"] == "success"
    assert "supprimé" in result["message"].lower()
    assert "container123" in result["message"]
    mock_client.containers.get.assert_called_once_with("container123")
    mock_container.remove.assert_called_once_with(force=True)


def test_docker_tool_remove_container_error(docker_tool):
    """Test that removing a container with an error raises RuntimeError."""
    mock_client = MagicMock()
    mock_client.containers.get.side_effect = Exception("Docker error")
    docker_tool._client = mock_client

    with pytest.raises(RuntimeError, match="Échec de la suppression du conteneur"):
        docker_tool.execute("remove_container", container_id="container123", force=True)


def test_docker_tool_unknown_operation(docker_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue"):
        docker_tool.execute("unknown")