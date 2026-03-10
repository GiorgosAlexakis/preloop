"""Tests for installer schemas."""

from datetime import datetime

from preloop.schemas.installers import InstallerVersionStat, InstallerDownloadStats


class TestInstallerVersionStat:
    """Test InstallerVersionStat schema."""

    def test_valid_schema(self):
        """Valid version stat parses correctly."""
        stat = InstallerVersionStat(version="1.0.0", count=42)
        assert stat.version == "1.0.0"
        assert stat.count == 42

    def test_model_dump(self):
        """Model serializes to dict."""
        stat = InstallerVersionStat(version="2.1.0", count=100)
        data = stat.model_dump()
        assert data["version"] == "2.1.0"
        assert data["count"] == 100


class TestInstallerDownloadStats:
    """Test InstallerDownloadStats schema."""

    def test_minimal_valid_schema(self):
        """Minimal valid stats parse correctly."""
        stats = InstallerDownloadStats(
            audit_enabled=True,
            days=7,
            total_downloads=100,
            downloads_last_24h=10,
            unique_ips=50,
            cli_downloads=60,
            oss_downloads=30,
            pinned_downloads=5,
            latest_version_downloads=20,
        )
        assert stats.audit_enabled is True
        assert stats.days == 7
        assert stats.total_downloads == 100
        assert stats.downloads_last_24h == 10
        assert stats.unique_ips == 50
        assert stats.last_download_at is None
        assert stats.top_versions == []

    def test_with_optional_fields(self):
        """Stats with optional fields parse correctly."""
        now = datetime.now()
        stats = InstallerDownloadStats(
            audit_enabled=False,
            days=30,
            total_downloads=500,
            downloads_last_24h=25,
            unique_ips=200,
            cli_downloads=300,
            oss_downloads=150,
            pinned_downloads=50,
            latest_version_downloads=100,
            last_download_at=now,
            top_versions=[
                InstallerVersionStat(version="1.0.0", count=200),
                InstallerVersionStat(version="0.9.0", count=100),
            ],
        )
        assert stats.last_download_at == now
        assert len(stats.top_versions) == 2
        assert stats.top_versions[0].version == "1.0.0"
        assert stats.top_versions[0].count == 200
