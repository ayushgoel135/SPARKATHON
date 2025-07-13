import pandas as pd
import numpy as np
from django.db import models
from django.db.models import Q, Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.arima.model import ARIMA
from prophet import Prophet
import holidays
from django.conf import settings
import joblib
import os
from datetime import datetime, timedelta
import json
from ..models import SalesHistory, DemandForecast, Product, Warehouse, Inventory

class DemandForecaster:
    def __init__(self, product_id, warehouse_id):
        self.product_id = product_id
        self.warehouse_id = warehouse_id
        self.model_dir = os.path.join(settings.MODEL_ROOT, 'forecasting')
        os.makedirs(self.model_dir, exist_ok=True)
        self.model_path = os.path.join(self.model_dir, f"model_{product_id}_{warehouse_id}.pkl")
        self.scaler_path = os.path.join(self.model_dir, f"scaler_{product_id}_{warehouse_id}.pkl")
        
    def prepare_data(self, lookback_days=730):
        """Prepare training data with features"""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=lookback_days)
        
        sales_data = SalesHistory.objects.filter(
            product_id=self.product_id,
            warehouse_id=self.warehouse_id,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        if not sales_data:
            raise ValueError("No sales data available for forecasting")
            
        df = pd.DataFrame(list(sales_data.values(
            'date', 'quantity_sold', 'promotion_flag', 'weather_condition', 'special_event'
        )))
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Add time features
        df['day_of_week'] = df.index.dayofweek
        df['day_of_month'] = df.index.day
        df['month'] = df.index.month
        df['year'] = df.index.year
        df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        df['is_month_start'] = df.index.is_month_start.astype(int)
        df['is_month_end'] = df.index.is_month_end.astype(int)
        
        # Add holiday information
        country_holidays = holidays.CountryHoliday('US')  # Adjust for your country
        df['is_holiday'] = df.index.to_series().apply(lambda x: x in country_holidays).astype(int)
        
        # Add lag features
        for lag in [1, 7, 14, 30]:
            df[f'lag_{lag}'] = df['quantity_sold'].shift(lag)
        
        # Add rolling features
        df['rolling_7_mean'] = df['quantity_sold'].rolling(7).mean()
        df['rolling_30_mean'] = df['quantity_sold'].rolling(30).mean()
        
        # Handle categorical features
        df = pd.get_dummies(df, columns=['weather_condition', 'special_event'], dummy_na=True)
        
        # Fill missing values
        df.fillna(method='ffill', inplace=True)
        df.fillna(0, inplace=True)
        
        return df
    
    def train_model(self, method='random_forest'):
        """Train and evaluate forecasting model"""
        df = self.prepare_data()
        X = df.drop('quantity_sold', axis=1)
        y = df['quantity_sold']
        
        # Time-series cross-validation
        tscv = TimeSeriesSplit(n_splits=5)
        
        if method == 'random_forest':
            model = RandomForestRegressor(
                n_estimators=200,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
        elif method == 'gradient_boost':
            model = GradientBoostingRegressor(
                n_estimators=150,
                max_depth=5,
                random_state=42
            )
        else:
            raise ValueError("Unsupported model type")
        
        # Cross-validation
        scores = cross_val_score(
            model, X, y, cv=tscv, 
            scoring='neg_mean_absolute_error'
        )
        mae_scores = -scores
        
        # Train final model
        model.fit(X, y)
        
        # Save model
        joblib.dump(model, self.model_path)
        
        return {
            'model': method,
            'avg_mae': mae_scores.mean(),
            'std_mae': mae_scores.std(),
            'feature_importances': dict(zip(X.columns, model.feature_importances_))
        }
    
    def forecast_prophet(self, periods=30):
        """Forecast using Facebook's Prophet"""
        df = self.prepare_data()
        prophet_df = df.reset_index()[['date', 'quantity_sold']].rename(
            columns={'date': 'ds', 'quantity_sold': 'y'}
        )
        
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05
        )
        model.fit(prophet_df)
        
        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)
        
        # Extract forecasted values
        forecast_df = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(periods)
        forecast_df.set_index('ds', inplace=True)
        
        return forecast_df['yhat']
    
    def generate_forecast(self, method='random_forest', periods=30):
        """Generate forecast using specified method"""
        if method in ['random_forest', 'gradient_boost']:
            if not os.path.exists(self.model_path):
                self.train_model(method)
            
            model = joblib.load(self.model_path)
            df = self.prepare_data()
            
            # Create future dataframe
            last_date = df.index[-1]
            future_dates = pd.date_range(
                start=last_date + timedelta(days=1),
                end=last_date + timedelta(days=periods)
            )
            
            future_df = pd.DataFrame(index=future_dates)
            
            # Add time features
            future_df['day_of_week'] = future_df.index.dayofweek
            future_df['day_of_month'] = future_df.index.day
            future_df['month'] = future_df.index.month
            future_df['year'] = future_df.index.year
            future_df['is_weekend'] = future_df['day_of_week'].isin([5, 6]).astype(int)
            future_df['is_month_start'] = future_df.index.is_month_start.astype(int)
            future_df['is_month_end'] = future_df.index.is_month_end.astype(int)
            
            # Add holiday information
            country_holidays = holidays.CountryHoliday('US')
            future_df['is_holiday'] = future_df.index.to_series().apply(
                lambda x: x in country_holidays
            ).astype(int)
            
            # Add lag features using last known values
            for lag in [1, 7, 14, 30]:
                future_df[f'lag_{lag}'] = df['quantity_sold'].iloc[-lag]
            
            # Add rolling features
            future_df['rolling_7_mean'] = df['quantity_sold'].rolling(7).mean().iloc[-1]
            future_df['rolling_30_mean'] = df['quantity_sold'].rolling(30).mean().iloc[-1]
            
            # Add other features with last known values
            for col in df.columns:
                if col not in future_df.columns and col != 'quantity_sold':
                    if df[col].dtype == 'bool':
                        future_df[col] = df[col].iloc[-1]
                    elif df[col].dtype == 'object':
                        # For categoricals, use the most frequent value
                        future_df[col] = df[col].mode()[0]
                    else:
                        future_df[col] = df[col].iloc[-1]
            
            # Ensure all columns match training data
            missing_cols = set(df.columns) - set(future_df.columns)
            for col in missing_cols:
                future_df[col] = 0
            
            future_df = future_df[df.drop('quantity_sold', axis=1).columns]
            
            # Generate forecast
            forecast_values = model.predict(future_df)
            forecast_series = pd.Series(
                [max(0, round(x, 2)) for x in forecast_values],
                index=future_dates
            )
            
        elif method == 'prophet':
            forecast_series = self.forecast_prophet(periods)
        else:
            raise ValueError("Invalid forecasting method")
        
        # Save forecast to database
        forecast_dict = {
            str(date.date()): value for date, value in forecast_series.items()
        }
        
        forecast = DemandForecast(
            product_id=self.product_id,
            warehouse_id=self.warehouse_id,
            forecast_date=datetime.now().date(),
            period='daily',
            forecast_start=forecast_series.index[0].date(),
            forecast_end=forecast_series.index[-1].date(),
            forecast_values=forecast_dict,
            algorithm_used=method
        )
        forecast.save()
        
        return forecast