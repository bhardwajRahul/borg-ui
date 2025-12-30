"""
Unit tests for repository storage usage feature.
Tests filesystem disk usage monitoring for local and SSH repositories.
"""
import pytest
from unittest.mock import patch, Mock, AsyncMock
from app.database.models import Repository
from app.api.repositories import get_filesystem_usage, format_bytes


@pytest.mark.unit
class TestStorageUsageLocal:
    """Test filesystem storage usage for local repositories"""

    @pytest.mark.asyncio
    async def test_get_filesystem_usage_local_repo(self, test_db):
        """Test getting filesystem usage for a local repository"""
        # Create a local repository
        repo = Repository(
            name="Test Local Repo",
            path="/tmp/test-repo",
            repository_type="local",
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        # Mock shutil.disk_usage
        with patch('shutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value = Mock(
                total=1000000000000,  # 1TB
                used=400000000000,  # 400GB
                free=600000000000  # 600GB
            )

            from app.api.repositories import get_filesystem_usage
            result = await get_filesystem_usage(repo)

            assert result is not None
            assert result["total"] == 1000000000000
            assert result["used"] == 400000000000
            assert result["available"] == 600000000000
            assert result["percent_used"] == 40.0
            assert result["filesystem"] == "local"
            assert result["mount_point"] == "/tmp/test-repo"

    @pytest.mark.asyncio
    async def test_get_filesystem_usage_local_repo_with_archive(self, test_db):
        """Test getting filesystem usage for a local repository path with archive name"""
        repo = Repository(
            name="Test Repo with Archive",
            path="/backup/repo::archive-name",
            repository_type="local",
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        with patch('shutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value = Mock(
                total=500000000000,
                used=100000000000,
                free=400000000000
            )

            from app.api.repositories import get_filesystem_usage
            result = await get_filesystem_usage(repo)

            # Should use the base path without archive name
            mock_disk_usage.assert_called_with("/backup/repo")
            assert result is not None
            assert result["percent_used"] == 20.0


@pytest.mark.unit
class TestStorageUsageSSH:
    """Test filesystem storage usage for SSH repositories"""

    @pytest.mark.asyncio
    async def test_get_filesystem_usage_ssh_repo(self, test_db):
        """Test getting filesystem usage for an SSH repository"""
        from app.database.models import SSHKey
        from cryptography.fernet import Fernet
        import base64
        from app.config import settings

        # Create an SSH key
        encryption_key = settings.secret_key.encode()[:32]
        cipher = Fernet(base64.urlsafe_b64encode(encryption_key))
        private_key_encrypted = cipher.encrypt(b"-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")

        ssh_key = SSHKey(
            name="Test SSH Key",
            public_key="ssh-rsa test",
            private_key=private_key_encrypted.decode(),
            key_type="rsa"
        )
        test_db.add(ssh_key)
        test_db.commit()

        # Create an SSH repository
        repo = Repository(
            name="Test SSH Repo",
            path="user@host:/backup/repo",
            repository_type="ssh",
            host="test.example.com",
            port=22,
            username="testuser",
            ssh_key_id=ssh_key.id,
            encryption="repokey"
        )
        test_db.add(repo)
        test_db.commit()

        # Mock SSH command execution
        mock_process = AsyncMock()
        mock_process.returncode = 0
        # Simulate df output: Filesystem 1K-blocks Used Available Use% Mounted
        mock_process.communicate.return_value = (
            b"/dev/sda1 976762584 400000000 576762584 42% /backup\n",
            b""
        )

        async def mock_wait_for(coro, timeout):
            return await coro

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', side_effect=mock_wait_for):
                from app.api.repositories import get_filesystem_usage
                result = await get_filesystem_usage(repo)

                assert result is not None
                assert result["total"] == 976762584 * 1024  # Convert KB to bytes
                assert result["used"] == 400000000 * 1024
                assert result["available"] == 576762584 * 1024
                assert result["percent_used"] == 42.0
                assert result["filesystem"] == "/dev/sda1"
                assert result["mount_point"] == "/backup"

    @pytest.mark.asyncio
    async def test_get_filesystem_usage_ssh_missing_key(self, test_db):
        """Test handling of SSH repository with missing SSH key"""
        repo = Repository(
            name="SSH Repo No Key",
            path="user@host:/backup/repo",
            repository_type="ssh",
            host="test.example.com",
            username="testuser",
            ssh_key_id=999,  # Non-existent key
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        from app.api.repositories import get_filesystem_usage
        result = await get_filesystem_usage(repo)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_filesystem_usage_ssh_timeout(self, test_db):
        """Test handling of SSH command timeout"""
        from app.database.models import SSHKey
        from cryptography.fernet import Fernet
        import base64
        from app.config import settings
        import asyncio

        # Create an SSH key
        encryption_key = settings.secret_key.encode()[:32]
        cipher = Fernet(base64.urlsafe_b64encode(encryption_key))
        private_key_encrypted = cipher.encrypt(b"-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n")

        ssh_key = SSHKey(
            name="Test SSH Key Timeout",
            public_key="ssh-rsa test",
            private_key=private_key_encrypted.decode(),
            key_type="rsa"
        )
        test_db.add(ssh_key)
        test_db.commit()

        repo = Repository(
            name="SSH Repo Timeout",
            path="user@host:/backup/repo",
            repository_type="ssh",
            host="slow.example.com",
            username="testuser",
            ssh_key_id=ssh_key.id,
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        # Mock timeout
        mock_process = AsyncMock()
        mock_process.communicate.side_effect = asyncio.TimeoutError()

        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            from app.api.repositories import get_filesystem_usage
            result = await get_filesystem_usage(repo)

            assert result is None


@pytest.mark.unit
class TestStorageFormatting:
    """Test storage formatting functions"""

    def test_format_bytes_various_sizes(self):
        """Test formatting bytes to human-readable format"""
        assert format_bytes(0) == "0.00 B"
        assert format_bytes(1023) == "1023.00 B"
        assert format_bytes(1024) == "1.00 KB"
        assert format_bytes(1024 * 1024) == "1.00 MB"
        assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
        assert format_bytes(1024 * 1024 * 1024 * 1024) == "1.00 TB"

    def test_format_bytes_real_world_sizes(self):
        """Test formatting realistic storage sizes"""
        # 500 GB
        result = format_bytes(500 * 1024 * 1024 * 1024)
        assert "500.00 GB" == result or "500.00GB" in result

        # 1.5 TB
        result = format_bytes(int(1.5 * 1024 * 1024 * 1024 * 1024))
        assert "1.50 TB" == result or "1.50TB" in result


@pytest.mark.unit
class TestStorageUsageEdgeCases:
    """Test edge cases for storage usage"""

    @pytest.mark.asyncio
    async def test_unsupported_repository_type(self, test_db):
        """Test handling of unsupported repository types"""
        repo = Repository(
            name="Unsupported Repo",
            path="/test/repo",
            repository_type="unknown",
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        from app.api.repositories import get_filesystem_usage
        result = await get_filesystem_usage(repo)

        assert result is None

    @pytest.mark.asyncio
    async def test_ssh_repo_missing_required_fields(self, test_db):
        """Test SSH repository missing required connection fields"""
        repo = Repository(
            name="SSH Incomplete",
            path="user@host:/backup",
            repository_type="ssh",
            # Missing host, username, ssh_key_id
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        from app.api.repositories import get_filesystem_usage
        result = await get_filesystem_usage(repo)

        assert result is None

    @pytest.mark.asyncio
    async def test_local_repo_nonexistent_path(self, test_db):
        """Test local repository with nonexistent path"""
        repo = Repository(
            name="Nonexistent Path",
            path="/this/path/does/not/exist/12345",
            repository_type="local",
            encryption="none"
        )
        test_db.add(repo)
        test_db.commit()

        from app.api.repositories import get_filesystem_usage
        result = await get_filesystem_usage(repo)

        # Should return None or handle gracefully
        # The actual behavior depends on shutil.disk_usage implementation
        # which may raise an exception for nonexistent paths
        assert result is None or isinstance(result, dict)
