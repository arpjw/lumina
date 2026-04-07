use anyhow::{Context, Result};
use chrono::{Duration, Utc};
use reqwest::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use tracing::info;

use super::RawRecord;

pub struct GdeltSource {
    client: Client,
    lookback_days: i64,
}

#[derive(Debug, Deserialize)]
struct GdeltArticle {
    #[serde(rename = "seendate")]
    seen_date: Option<String>,
    url: Option<String>,
    title: Option<String>,
    #[serde(rename = "sourcecountry")]
    source_country: Option<String>,
    #[serde(rename = "sourcelang")]
    source_lang: Option<String>,
    tone: Option<f64>,
    #[serde(rename = "goldsteinscale")]
    goldstein_scale: Option<f64>,
}

#[derive(Debug, Deserialize)]
struct GdeltResponse {
    articles: Option<Vec<GdeltArticle>>,
}

impl GdeltSource {
    pub fn from_env() -> Result<Self> {
        let lookback_days = std::env::var("GDELT_LOOKBACK_DAYS")
            .unwrap_or_else(|_| "7".to_string())
            .parse::<i64>()
            .unwrap_or(7);

        Ok(Self {
            client: Client::builder()
                .user_agent("lumina-research/0.1")
                .timeout(std::time::Duration::from_secs(30))
                .build()?,
            lookback_days,
        })
    }

    pub async fn fetch(&self) -> Result<Vec<RawRecord>> {
        let queries = vec![
            "Federal Reserve interest rates monetary policy",
            "inflation CPI economic recession",
            "geopolitical risk sanctions war",
            "credit markets yield spread default",
            "China economy trade dollar",
        ];

        let mut all_records = Vec::new();

        for query in &queries {
            info!("GDELT querying: {}", query);
            match self.fetch_query(query).await {
                Ok(records) => all_records.extend(records),
                Err(e) => tracing::warn!("GDELT query failed for '{}': {}", query, e),
            }
            tokio::time::sleep(std::time::Duration::from_millis(500)).await;
        }

        all_records.sort_by(|a, b| b.timestamp.cmp(&a.timestamp));
        all_records.dedup_by_key(|r| r.id.clone());

        Ok(all_records)
    }

    async fn fetch_query(&self, query: &str) -> Result<Vec<RawRecord>> {
        let start = Utc::now() - Duration::days(self.lookback_days);
        let start_str = start.format("%Y%m%d%H%M%S").to_string();
        let end_str = Utc::now().format("%Y%m%d%H%M%S").to_string();

        let url = format!(
            "https://api.gdeltproject.org/api/v2/doc/doc?query={}&mode=artlist&maxrecords=250&startdatetime={}&enddatetime={}&format=json&sourcelang=english",
            urlencoding::encode(query),
            start_str,
            end_str,
        );

        let resp = self.client.get(&url).send().await.context("GDELT request failed")?;
        let gdelt: GdeltResponse = resp.json().await.context("GDELT JSON parse failed")?;

        let articles = gdelt.articles.unwrap_or_default();
        let records = articles
            .into_iter()
            .filter_map(|a| {
                let title = a.title.unwrap_or_default();
                if title.is_empty() {
                    return None;
                }
                let url_str = a.url.clone().unwrap_or_default();
                let mut hasher = Sha256::new();
                hasher.update(url_str.as_bytes());
                let id = format!("gdelt_{}", hex::encode(&hasher.finalize()[..8]));

                let timestamp = a.seen_date
                    .as_deref()
                    .and_then(|d| chrono::NaiveDateTime::parse_from_str(d, "%Y%m%dT%H%M%SZ").ok())
                    .map(|dt| dt.and_utc())
                    .unwrap_or_else(Utc::now);

                Some(RawRecord {
                    id,
                    source: "gdelt".to_string(),
                    source_type: "news".to_string(),
                    timestamp,
                    title: Some(title.clone()),
                    body: title,
                    url: a.url,
                    metadata: serde_json::json!({
                        "query": query,
                        "source_country": a.source_country,
                        "source_lang": a.source_lang,
                        "tone": a.tone,
                        "goldstein_scale": a.goldstein_scale,
                    }),
                })
            })
            .collect();

        Ok(records)
    }
}
