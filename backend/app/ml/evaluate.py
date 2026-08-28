from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class ModelEvaluator:
    @staticmethod
    def evaluate(
        y_true: Union[np.ndarray, pd.Series[Any]],
        y_pred: Union[np.ndarray, pd.Series[Any]],
        feature_names: Optional[List[str]] = None,
        model=None,
    ) -> Dict[str, Any]:
        """
        Computes genuine regression evaluation metrics and tree feature importances.
        """
        y_true = np.array(y_true, dtype=float)
        y_pred = np.array(y_pred, dtype=float)

        if len(y_true) == 0 or len(y_pred) == 0:
            return {
                "mae": 0.0,
                "rmse": 0.0,
                "r2_score": 0.0,
                "mape_pct": 0.0,
                "wape_pct": 0.0,
                "sample_count": 0,
                "feature_importances": []
            }

        mae = float(mean_absolute_error(y_true, y_pred))
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        r2 = float(r2_score(y_true, y_pred)) if len(y_true) >= 2 else 0.0

        # Avoid zero division in MAPE
        mask = y_true > 0
        mape = float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0) if np.sum(mask) > 0 else 0.0

        # WAPE (Weighted Absolute Percentage Error)
        sum_actual = float(np.sum(y_true))
        wape = float((np.sum(np.abs(y_true - y_pred)) / sum_actual) * 100.0) if sum_actual > 0 else 0.0

        # Feature importances
        feature_importance_list = []
        if model is not None and hasattr(model, "feature_importances_") and feature_names:
            importances = model.feature_importances_
            sorted_idx = np.argsort(importances)[::-1]
            for idx in sorted_idx:
                if idx < len(feature_names):
                    feature_importance_list.append({
                        "feature": feature_names[idx],
                        "importance_pct": round(float(importances[idx]) * 100.0, 2)
                    })

        return {
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2_score": round(r2, 4),
            "mape_pct": round(mape, 2),
            "wape_pct": round(wape, 2),
            "sample_count": len(y_true),
            "feature_importances": feature_importance_list
        }
