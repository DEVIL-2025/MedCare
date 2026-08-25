import pandas as pd
import numpy as np
from typing import Tuple, List

FEATURE_COLUMNS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "lag_21",
    "rolling_mean_7d",
    "rolling_std_7d",
    "rolling_mean_14d",
    "rolling_mean_30d",
    "velocity_ratio",
    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",
    "seasonal_uplift_pct",
    "distributor_orders_count",
    "is_promotional",
    "unit_cost",
]


class FeatureEngineeringService:
    @staticmethod
    def construct_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes lag features, rolling statistics, velocity signals, and calendar attributes per SKU-DC.
        """
        if df.empty:
            return df

        df = df.sort_values(by=["sku", "warehouse_id", "date"]).reset_index(drop=True)
        grouped = df.groupby(["sku", "warehouse_id"])

        # Lag features
        df["lag_1"] = grouped["actual_demand"].shift(1)
        df["lag_7"] = grouped["actual_demand"].shift(7)
        df["lag_14"] = grouped["actual_demand"].shift(14)
        df["lag_21"] = grouped["actual_demand"].shift(21)

        # Fill lag NaNs with current actual
        for col in ["lag_1", "lag_7", "lag_14", "lag_21"]:
            df[col] = df[col].fillna(df["actual_demand"])

        # Fast rolling statistics
        df["rolling_mean_7d"] = df["lag_1"].rolling(7, min_periods=1).mean()
        df["rolling_std_7d"] = df["lag_1"].rolling(7, min_periods=1).std().fillna(0)
        df["rolling_mean_14d"] = df["lag_1"].rolling(14, min_periods=1).mean()
        df["rolling_mean_30d"] = df["lag_1"].rolling(30, min_periods=1).mean()

        # Velocity ratio
        df["velocity_ratio"] = (df["rolling_mean_7d"] / (df["rolling_mean_30d"] + 1e-5)).fillna(1.0)

        # Calendar features
        df["day_of_week"] = df["date"].dt.dayofweek
        df["day_of_month"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["is_weekend"] = df["day_of_week"].apply(lambda d: 1 if d >= 5 else 0)

        return df

    @staticmethod
    def get_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Extracts the input feature matrix X and target y.
        """
        df_clean = df.dropna(subset=FEATURE_COLUMNS + ["actual_demand"])
        X = df_clean[FEATURE_COLUMNS]
        y = df_clean["actual_demand"]
        return X, y
