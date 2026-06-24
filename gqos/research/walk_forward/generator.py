from typing import Optional
from dateutil.relativedelta import relativedelta
from gqos.research.dataset import TimeRange
from gqos.research.walk_forward.models import WalkForwardFold, FoldManifest

class WalkForwardGenerator:
    def __init__(self, dataset_hash: str):
        self.dataset_hash = dataset_hash

    def generate_rolling_folds(
        self,
        master_window: TimeRange,
        train_duration: relativedelta,
        test_duration: relativedelta,
        gap_duration: Optional[relativedelta] = None
    ) -> FoldManifest:
        """
        Generates sliding window folds. The train window size remains fixed.
        """
        folds = []
        current_train_start = master_window.start_date
        
        while True:
            train_end = current_train_start + train_duration
            
            if gap_duration:
                gap_start = train_end
                gap_end = gap_start + gap_duration
                test_start = gap_end
                gap_window = TimeRange(start_date=gap_start, end_date=gap_end)
            else:
                test_start = train_end
                gap_window = None
                
            test_end = test_start + test_duration
            
            if test_end > master_window.end_date:
                # Stop if the test window goes beyond the master data available
                break
                
            train_window = TimeRange(start_date=current_train_start, end_date=train_end)
            test_window = TimeRange(start_date=test_start, end_date=test_end)
            
            fold = WalkForwardFold(
                dataset_hash=self.dataset_hash,
                train_window=train_window,
                test_window=test_window,
                gap_window=gap_window
            )
            fold.validate_leakage()
            folds.append(fold)
            
            # Step forward by the test duration for non-overlapping out-of-sample execution
            current_train_start += test_duration
            
        return FoldManifest(folds=folds)

    def generate_expanding_folds(
        self,
        master_window: TimeRange,
        initial_train_duration: relativedelta,
        test_duration: relativedelta,
        gap_duration: Optional[relativedelta] = None
    ) -> FoldManifest:
        """
        Generates expanding window folds. The train window start remains anchored.
        """
        folds = []
        anchored_train_start = master_window.start_date
        current_train_end = anchored_train_start + initial_train_duration
        
        while True:
            if gap_duration:
                gap_start = current_train_end
                gap_end = gap_start + gap_duration
                test_start = gap_end
                gap_window = TimeRange(start_date=gap_start, end_date=gap_end)
            else:
                test_start = current_train_end
                gap_window = None
                
            test_end = test_start + test_duration
            
            if test_end > master_window.end_date:
                break
                
            train_window = TimeRange(start_date=anchored_train_start, end_date=current_train_end)
            test_window = TimeRange(start_date=test_start, end_date=test_end)
            
            fold = WalkForwardFold(
                dataset_hash=self.dataset_hash,
                train_window=train_window,
                test_window=test_window,
                gap_window=gap_window
            )
            fold.validate_leakage()
            folds.append(fold)
            
            # Expand the train window by the test duration
            current_train_end += test_duration
            
        return FoldManifest(folds=folds)
