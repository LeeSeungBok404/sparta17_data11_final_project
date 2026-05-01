import json
from pathlib import Path
import pandas as pd
import numpy as np


def ensure_dir(path: Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def ensure_parent_dir(file_path: Path) -> None:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)


def load_csv_safe(path: Path, encoding: str = "utf-8-sig") -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {path}")
    return pd.read_csv(path, encoding=encoding)


def save_csv_safe(df: pd.DataFrame, path: Path, encoding: str = "utf-8-sig") -> None:
    path = Path(path)
    ensure_parent_dir(path)
    df.to_csv(path, index=False, encoding=encoding)


def append_csv_safe(df: pd.DataFrame, path: Path, encoding: str = "utf-8-sig") -> None:
    path = Path(path)
    ensure_parent_dir(path)
    write_header = not path.exists()
    df.to_csv(path, mode="a", index=False, header=write_header, encoding=encoding)


def load_json(path: Path, default):
    path = Path(path)
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: Path, data) -> None:
    path = Path(path)
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["", "nan", "None", "NaN"]), col] = np.nan
    return df


def convert_numeric_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def print_kv(title: str, value) -> None:
    print(f"{title}: {value}")


def print_section(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def first_existing_path(paths: list[Path]) -> Path | None:
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None