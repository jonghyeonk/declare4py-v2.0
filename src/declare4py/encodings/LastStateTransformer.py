from sklearn.base import TransformerMixin
import pandas as pd
from time import time

class LastStateTransformer(TransformerMixin):
    
    def __init__(self, case_id_col, cat_cols, num_cols, fillna=True):
        """
        Parameters
        -------------------
        case_id_col
            a column indicating the case identifier in an event log
        cat_cols
            columns indicating the categorical attributes in an event log
        num_cols
            columns indicating the numerical attributes in an event log       
        fillna
            TRUE: replace NA to 0 value in dataframe / FALSE: keep NA        
        """

        self.case_id_col = case_id_col
        self.cat_cols = cat_cols
        self.num_cols = num_cols
        self.fillna = fillna
        
        self.columns = None
        
        self.fit_time = 0
        self.transform_time = 0
        
    
    def fit(self, X, y=None):
        return self
    
    
    def transform(self, X, y=None):
        """
        Tranforms the event log into a last-state encoded matrix:


        Parameters
        -------------------
        X
            Event log / Pandas dataframe
        Returns
        ------------------
        transformed_log
            Transformed event log
        """
        
        start = time()
        
        dt_last = X.groupby(self.case_id_col).last()
        
        # transform numeric cols
        dt_transformed = dt_last[self.num_cols]
        
        # transform cat cols
        if len(self.cat_cols) > 0:
            dt_cat = pd.get_dummies(dt_last[self.cat_cols])
            dt_transformed = pd.concat([dt_transformed, dt_cat], axis=1)
        
        # fill NA with 0 if requested
        if self.fillna:
            dt_transformed = dt_transformed.fillna(0)
            
        # add missing columns if necessary
        if self.columns is not None:
            missing_cols = [col for col in self.columns if col not in dt_transformed.columns]
            for col in missing_cols:
                dt_transformed[col] = 0
            dt_transformed = dt_transformed[self.columns]
        else:
            self.columns = dt_transformed.columns
        
        self.transform_time = time() - start
        return dt_transformed
    
    def get_feature_names(self):
        return self.columns
    