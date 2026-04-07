use anyhow::{Context, Result};
use chrono::Utc;
use reqwest::Client;
use serde::Deserialize;
use tracing::info;

use super::RawRecord;

pub struct FredSource {
    client: Client,
    api_key: String,
    series: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct FredResponse {
    observations: Vec<FredObservation>,
}

#[derive(Debug, Deserialize)]
struct FredObservation {
    date: String,
    value: String,
}

impl FredSource {
    pub fn from_env() -> Result<Self> {
        let api_key = std::env::var("FRED_API_KEY").context("FRED_API_KEY not set")?;
        let series = std::env::var("FRED_SERIES")
            .unwrap_or_else(|_| "UNRATE,CPIAUCSL,DGS10,DGS2,VIXCLS".to_string())
            .split(',')
            .map(|s| s.trim().to_string())
            .collect();

        Ok(Self {
            client: Client::builder()
                .user_agent("lumina-research/0.1")
                .timeout(std::time::Duration::from_secs(30))
                .build()?,
            api_key,
            series,
        })
    }

    pub async fn fetch(&self) -> Result<Vec<RawRecord>> {
        let mut all_records = Vec::new();

        for series_id in &self.series {
            info!("FRED fetching series: {}", series_id);
            match self.fetch_series(series_id).await {
                Ok(records) => all_records.extend(records),
                Err(e) => tracing::warn!("FRED series {} failed: {}", series_id, e),
            }
            tokio::time::sleep(std::time::Duration::from_millis(200)).await;
        }

        Ok(all_records)
    }

    async fn fetch_series(&self, series_id: &str) -> Result<Vec<RawRecord>> {
        let url = format!(
            "https://api.stlouisfed.org/fred/series/observations?series_id={}&api_key={}&file_type=json&limit=252&sort_order=desc",
            series_id, self.api_key
        );

        let resp = self.client.get(&url).send().await.context("FRED request failed")?;
        let fred: FredResponse = resp.json().await.context("FRED JSON failed")?;

        let records = fred.observations
            .into_iter()
            .filter(|obs| obs.value != "." && !obs.value.is_empty())
            .map(|obs| {
                let value: f64 = obs.value.parse().unwrap_or(0.0);
                let id = format!("fred_{}_{}", series_id, obs.date.replace('-', ""));
                let timestamp = chrono::NaiveDate::parse_from_str(&obs.date, "%Y-%m-%d")
                    .map(|d| d.and_hms_opt(0, 0, 0).unwrap().and_utc())
                    .unwrap_or_else(|_| Utc::now());

                RawRecord {
                    id,
                    source: "fred".to_string(),
                    source_type: "macro".to_string(),
                    timestamp,
                    title: Some(format!("{} = {}", series_id, value)),
                    body: format!("{}: {}", series_id, value),
                    url: Some(format!("https://fred.stlouisfed.org/series/{}", series_id)),
                    metadata: serde_json::json!({
                        "series_id": series_id,
                        "value": value,
                        "date": obs.date,
                    }),
                }
            })
            .collect();

        Ok(records)
    }
}
