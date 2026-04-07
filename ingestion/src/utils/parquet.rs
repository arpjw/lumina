use anyhow::Result;
use chrono::Utc;
use std::path::PathBuf;

use crate::sources::RawRecord;

pub struct ParquetSink {
    base_dir: PathBuf,
}

impl ParquetSink {
    pub fn new(base_dir: &str) -> Self {
        Self {
            base_dir: PathBuf::from(base_dir),
        }
    }

    pub async fn write(&self, source: &str, records: &[RawRecord]) -> Result<()> {
        if records.is_empty() {
            return Ok(());
        }

        let date = Utc::now().format("%Y-%m-%d").to_string();
        let dir = self.base_dir.join("raw").join(source).join(&date);
        tokio::fs::create_dir_all(&dir).await?;

        let path = dir.join("data.jsonl");
        let mut content = String::new();

        for record in records {
            let line = serde_json::to_string(record)?;
            content.push_str(&line);
            content.push('\n');
        }

        tokio::fs::write(&path, content).await?;
        tracing::info!("Wrote {} records to {:?}", records.len(), path);

        Ok(())
    }
}
