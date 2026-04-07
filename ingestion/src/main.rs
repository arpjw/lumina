mod sources;
mod utils;

use anyhow::Result;
use clap::{Parser, Subcommand};
use dotenv::dotenv;
use tracing::info;
use tracing_subscriber::EnvFilter;

use sources::{edgar::EdgarSource, fred::FredSource, gdelt::GdeltSource, reddit::RedditSource, wikipedia::WikipediaSource};
use utils::parquet::ParquetSink;

#[derive(Parser)]
#[command(name = "lumina-ingest", about = "Lumina alternative data ingestion pipeline")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    All,
    Reddit,
    Gdelt,
    Edgar,
    Fred,
    Wikipedia,
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    let cli = Cli::parse();
    let data_dir = std::env::var("DATA_DIR").unwrap_or_else(|_| "./data".to_string());
    let sink = ParquetSink::new(&data_dir);

    match cli.command {
        Commands::Reddit => {
            info!("Running Reddit ingestion");
            let source = RedditSource::from_env()?;
            let records = source.fetch().await?;
            sink.write("reddit", &records).await?;
            info!("Wrote {} Reddit records", records.len());
        }
        Commands::Gdelt => {
            info!("Running GDELT ingestion");
            let source = GdeltSource::from_env()?;
            let records = source.fetch().await?;
            sink.write("gdelt", &records).await?;
            info!("Wrote {} GDELT records", records.len());
        }
        Commands::Edgar => {
            info!("Running SEC EDGAR ingestion");
            let source = EdgarSource::from_env()?;
            let records = source.fetch().await?;
            sink.write("edgar", &records).await?;
            info!("Wrote {} EDGAR records", records.len());
        }
        Commands::Fred => {
            info!("Running FRED ingestion");
            let source = FredSource::from_env()?;
            let records = source.fetch().await?;
            sink.write("fred", &records).await?;
            info!("Wrote {} FRED records", records.len());
        }
        Commands::Wikipedia => {
            info!("Running Wikipedia event stream ingestion");
            let source = WikipediaSource::new();
            let records = source.fetch(500).await?;
            sink.write("wikipedia", &records).await?;
            info!("Wrote {} Wikipedia records", records.len());
        }
        Commands::All => {
            info!("Running full ingestion pipeline");
            let (reddit, gdelt, edgar, fred, wiki) = tokio::join!(
                async {
                    let s = RedditSource::from_env().unwrap();
                    s.fetch().await.unwrap_or_default()
                },
                async {
                    let s = GdeltSource::from_env().unwrap();
                    s.fetch().await.unwrap_or_default()
                },
                async {
                    let s = EdgarSource::from_env().unwrap();
                    s.fetch().await.unwrap_or_default()
                },
                async {
                    let s = FredSource::from_env().unwrap();
                    s.fetch().await.unwrap_or_default()
                },
                async {
                    let s = WikipediaSource::new();
                    s.fetch(500).await.unwrap_or_default()
                },
            );

            sink.write("reddit", &reddit).await?;
            sink.write("gdelt", &gdelt).await?;
            sink.write("edgar", &edgar).await?;
            sink.write("fred", &fred).await?;
            sink.write("wikipedia", &wiki).await?;

            info!(
                "Full ingestion complete: {} reddit, {} gdelt, {} edgar, {} fred, {} wikipedia",
                reddit.len(), gdelt.len(), edgar.len(), fred.len(), wiki.len()
            );
        }
    }

    Ok(())
}
