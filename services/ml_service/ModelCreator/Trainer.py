from sklearn.model_selection import train_test_split
from ModelCreator.Utiles.Validator import validate_columns
from ModelCreator.Utiles.Evaluator import evaluate_metrics
from ModelCreator.ModelLoader import ModelFactory

class ModelTrainer:
    def __init__(self, model_type, params_by_cluster, input_cols, test_size, target_col, cluster_enabled):
        self.model_type = model_type
        self.params_by_cluster = params_by_cluster
        self.input_cols = input_cols
        self.test_size = test_size
        self.target_col = target_col
        self.cluster_enabled = cluster_enabled

        self.models_by_cluster = {}

    def train_full_model(self, df, target_col):
        validate_columns(df, self.input_cols + [target_col])

        X = df[self.input_cols]
        y = df[target_col]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=self.test_size, random_state=42)

        model = ModelFactory.get_model(self.model_type, cluster_id="full", params_dict=self.params_by_cluster)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        self.models_by_cluster["full"] = model

        metrics = evaluate_metrics(y_test, y_pred)
        return metrics, X_test, y_test

    def train_by_cluster(self, df, cluster_col="cluster_id"):
        if not self.cluster_enabled:
            print("[INFO] 클러스터링 비활성화됨 → 전체 모델만 학습")
            return {}

        validate_columns(df, self.input_cols + [self.target_col, cluster_col])

        metrics_dict = {}

        for cluster_id in sorted(df[cluster_col].unique()):
            sub_df = df[df[cluster_col] == cluster_id]
            X = sub_df[self.input_cols]
            y = sub_df[self.target_col]

            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=self.test_size, random_state=42)

            model = ModelFactory.get_model(self.model_type, cluster_id=cluster_id, params_dict=self.params_by_cluster)
            model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            self.models_by_cluster[cluster_id] = model
            metrics_dict[cluster_id] = evaluate_metrics(y_test, y_pred)

        return metrics_dict