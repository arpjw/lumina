import os
import sys
import click
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "./data")


@click.group()
def cli():
    pass


@cli.command()
def sentiment():
    from nlp.sentiment import run
    logger.info("Running FinBERT sentiment scoring")
    run(DATA_DIR, DATA_DIR)
    logger.info("Sentiment complete")


@cli.command()
def topics():
    from nlp.topics import TopicEngine
    logger.info("Running BERTopic topic modeling")
    engine = TopicEngine()
    engine.process_raw_data(DATA_DIR)
    logger.info("Topics complete")


@cli.command()
def geopolitical():
    from nlp.geopolitical import process_gdelt_features
    logger.info("Running GDELT geopolitical feature extraction")
    process_gdelt_features(DATA_DIR)
    logger.info("Geopolitical features complete")


@cli.command()
def train():
    from training.regime_classifier import RegimeClassifier
    logger.info("Training regime classifier")
    clf = RegimeClassifier()
    metrics = clf.train(DATA_DIR)
    logger.info(f"Training complete: {metrics}")


@cli.command()
def predict():
    from training.regime_classifier import RegimeClassifier
    logger.info("Running regime prediction on latest data")
    clf = RegimeClassifier()
    result = clf.predict_latest(DATA_DIR)
    logger.info(f"Regime prediction: {result}")


@cli.command()
def shap():
    from training.regime_classifier import RegimeClassifier
    logger.info("Computing SHAP feature importance")
    clf = RegimeClassifier()
    df = clf.compute_shap(DATA_DIR)
    logger.info(f"Top features:\n{df.head(10).to_string()}")
    out_path = os.path.join(DATA_DIR, "features", "shap_importance.parquet")
    df.to_parquet(out_path, index=False)
    logger.info(f"SHAP saved to {out_path}")


@cli.command()
@click.pass_context
def all(ctx):
    logger.info("Running full pipeline: sentiment → topics → geopolitical → train → predict")
    ctx.invoke(sentiment)
    ctx.invoke(topics)
    ctx.invoke(geopolitical)
    ctx.invoke(train)
    ctx.invoke(predict)
    ctx.invoke(shap)
    logger.info("Full pipeline complete")


if __name__ == "__main__":
    cli()
