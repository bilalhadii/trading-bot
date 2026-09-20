from datetime import datetime, timezone

from data.historical_downloader import download_range


def main():

    download_range(
        ticker="AAPL",
        start=datetime(
            2024,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        end=datetime(
            2025,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        chunk_days=7,
    )


if __name__ == "__main__":
    main()