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

        # Group-isolated rolling statistics
        grouped_lag = df.groupby(["sku", "warehouse_id"])["lag_1"]
        df["rolling_mean_7d"] = grouped_lag.transform(lambda s: s.rolling(7, min_periods=1).mean())
        df["rolling_std_7d"] = grouped_lag.transform(lambda s: s.rolling(7, min_periods=1).std()).fillna(0.0)
        df["rolling_mean_14d"] = grouped_lag.transform(lambda s: s.rolling(14, min_periods=1).mean())
        df["rolling_mean_30d"] = grouped_lag.transform(lambda s: s.rolling(30, min_periods=1).mean())

        # Velocity ratio
        df["velocity_ratio"] = (df["rolling_mean_7d"] / (df["rolling_mean_30d"] + 1e-5)).fillna(1.0)

        # Calendar features
        df["day_of_week"] = df["date"].dt.dayofweek
        df["day_of_month"] = df["date"].dt.day
        df["month"] = df["date"].dt.month
        df["is_weekend"] = df["day_of_week"].apply(lambda d: 1 if d >= 5 else 0)

        return df

    @staticmethod
    def compute_step_features(
        buf: List[float],
        forecast_date,
        seasonal_uplift_pct: float,
        unit_cost: float
    ) -> List[float]:
        """
        Computes the exact 17-feature vector for a single multi-step rollout day,
        maintaining exact parity with construct_features() definitions.
        """
        lag_1 = float(buf[-1])
        lag_7 = float(buf[-7]) if len(buf) >= 7 else lag_1
        lag_14 = float(buf[-14]) if len(buf) >= 14 else lag_1
        lag_21 = float(buf[-21]) if len(buf) >= 21 else lag_1

        win_7 = buf[-7:]
        r_7 = float(np.mean(win_7))
        r_std_7 = float(np.std(win_7, ddof=1)) if len(win_7) >= 2 else 0.0
        if np.isnan(r_std_7):
            r_std_7 = 0.0

        r_14 = float(np.mean(buf[-14:]))
        r_30 = float(np.mean(buf[-30:]))
        vel_ratio = float(r_7 / (r_30 + 1e-5))

        dow = float(forecast_date.weekday())
        dom = float(forecast_date.day)
        month = float(forecast_date.month)
        is_weekend = 1.0 if dow >= 5.0 else 0.0

        s_uplift = float(seasonal_uplift_pct)
        dist_orders = 5.0 if s_uplift > 0.0 else 2.0
        is_promo = 1.0 if s_uplift > 0.0 else 0.0
        u_cost = float(unit_cost)

        return [
            lag_1, lag_7, lag_14, lag_21,
            r_7, r_std_7, r_14, r_30,
            vel_ratio, dow, dom, month, is_weekend,
            s_uplift, dist_orders, is_promo, u_cost
        ]

    @staticmethod
    def get_feature_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Extracts the input feature matrix X and target y.
        """
        df_clean = df.dropna(subset=FEATURE_COLUMNS + ["actual_demand"])
        X = df_clean[FEATURE_COLUMNS]
        y = df_clean["actual_demand"]
        return X, y
