use anyhow::{Context, Result};
use chrono::Utc;
use reqwest::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use tracing::info;

use super::RawRecord;

pub struct WikipediaSource {
    client: Client,
}

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct WikiEvent {
    title: Option<String>,
    comment: Option<String>,
    server_name: Option<String>,
    #[serde(rename = "type")]
    event_type: Option<String>,
    timestamp: Option<i64>,
    user: Option<String>,
    length: Option<WikiLength>,
}

#[derive(Debug, Deserialize)]
struct WikiLength {
    new: Option<i64>,
    old: Option<i64>,
}

impl WikipediaSource {
    pub fn new() -> Self {
        Self {
            client: Client::builder()
                .user_agent("lumina-research/0.1")
                .timeout(std::time::Duration::from_secs(60))
                .build()
                .unwrap(),
        }
    }

    pub async fn fetch(&self, max_events: usize) -> Result<Vec<RawRecord>> {
        info!("Wikipedia: streaming {} events from EventStream", max_events);

        let resp = self.client
            .get("https://stream.wikimedia.org/v2/stream/recentchange")
            .send()
            .await
            .context("Wikipedia stream connect failed")?;

        let mut records = Vec::new();
        let text = resp.text().await.unwrap_or_default();

        let macro_keywords = [
            "economy", "inflation", "recession", "federal reserve", "interest rate",
            "gdp", "unemployment", "monetary", "fiscal", "central bank",
            "geopolitics", "sanctions", "war", "trade", "tariff",
        ];

        for line in text.lines() {
            if records.len() >= max_events {
                break;
            }
            if !line.starts_with("data: ") {
                continue;
            }
            let json_str = &line[6..];
            let Ok(event) = serde_json::from_str::<WikiEvent>(json_str) else {
                continue;
            };

            let title = event.title.as_deref().unwrap_or("");
            let comment = event.comment.as_deref().unwrap_or("");
            let server = event.server_name.as_deref().unwrap_or("");

            if !server.contains("wikipedia.org") {
                continue;
            }
            if event.event_type.as_deref() != Some("edit") {
                continue;
            }

            let combined = format!("{} {}", title, comment).to_lowercase();
            let is_macro = macro_keywords.iter().any(|kw| combined.contains(kw));
            if !is_macro {
                continue;
            }

            let mut hasher = Sha256::new();
            hasher.update(format!("wiki_{}_{}", title, comment).as_bytes());
            let id = format!("wiki_{}", hex::encode(&hasher.finalize()[..8]));

            let timestamp = event.timestamp
                .map(|ts| chrono::DateTime::<Utc>::from_timestamp(ts, 0).unwrap_or_else(Utc::now))
                .unwrap_or_else(Utc::now);

            let delta = event.length.as_ref().map(|l| {
                l.new.unwrap_or(0) - l.old.unwrap_or(0)
            });

            records.push(RawRecord {
                id,
                source: "wikipedia".to_string(),
                source_type: "event".to_string(),
                timestamp,
                title: Some(title.to_string()),
                body: format!("{}: {}", title, comment),
                url: Some(format!("https://en.wikipedia.org/wiki/{}", title.replace(' ', "_"))),
                metadata: serde_json::json!({
                    "server": server,
                    "edit_delta": delta,
                    "user": event.user,
                }),
            });
        }

        info!("Wikipedia: collected {} macro-relevant events", records.len());
        Ok(records)
    }
}
