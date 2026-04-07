// edgar.rs
use anyhow::{Context, Result};
use chrono::Utc;
use reqwest::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use tracing::info;

use super::RawRecord;

pub struct EdgarSource {
    client: Client,
    form_types: Vec<String>,
    user_agent: String,
}

#[derive(Debug, Deserialize)]
struct EdgarFilingsResponse {
    hits: EdgarHits,
}

#[derive(Debug, Deserialize)]
struct EdgarHits {
    hits: Vec<EdgarHit>,
}

#[derive(Debug, Deserialize)]
struct EdgarHit {
    #[serde(rename = "_source")]
    source: EdgarFilingSource,
}

#[derive(Debug, Deserialize)]
struct EdgarFilingSource {
    #[serde(rename = "file_date")]
    file_date: Option<String>,
    #[serde(rename = "display_names")]
    display_names: Option<Vec<String>>,
    #[serde(rename = "form_type")]
    form_type: Option<String>,
    #[serde(rename = "period_of_report")]
    period_of_report: Option<String>,
    #[serde(rename = "entity_name")]
    entity_name: Option<String>,
    #[serde(rename = "file_num")]
    file_num: Option<String>,
}

impl EdgarSource {
    pub fn from_env() -> Result<Self> {
        let form_types = std::env::var("EDGAR_FORM_TYPES")
            .unwrap_or_else(|_| "8-K,10-K".to_string())
            .split(',')
            .map(|s| s.trim().to_string())
            .collect();

        let user_agent = std::env::var("EDGAR_USER_AGENT")
            .unwrap_or_else(|_| "Lumina Research research@example.com".to_string());

        Ok(Self {
            client: Client::builder()
                .user_agent(&user_agent)
                .timeout(std::time::Duration::from_secs(30))
                .build()?,
            form_types,
            user_agent,
        })
    }

    pub async fn fetch(&self) -> Result<Vec<RawRecord>> {
        let mut all_records = Vec::new();

        for form_type in &self.form_types {
            info!("EDGAR fetching form type: {}", form_type);
            match self.fetch_form(form_type).await {
                Ok(records) => all_records.extend(records),
                Err(e) => tracing::warn!("EDGAR form {} failed: {}", form_type, e),
            }
            tokio::time::sleep(std::time::Duration::from_millis(1000)).await;
        }

        Ok(all_records)
    }

    async fn fetch_form(&self, form_type: &str) -> Result<Vec<RawRecord>> {
        let url = format!(
            "https://efts.sec.gov/LATEST/search-index?q=\"{}\"&dateRange=custom&startdt={}&enddt={}&forms={}",
            form_type,
            (Utc::now() - chrono::Duration::days(30)).format("%Y-%m-%d"),
            Utc::now().format("%Y-%m-%d"),
            form_type,
        );

        let resp = self.client
            .get(&url)
            .header("User-Agent", &self.user_agent)
            .send()
            .await
            .context("EDGAR request failed")?;

        let edgar: EdgarFilingsResponse = resp.json().await.context("EDGAR JSON failed")?;

        let records = edgar.hits.hits
            .into_iter()
            .filter_map(|hit| {
                let s = hit.source;
                let entity = s.entity_name.as_deref().unwrap_or("Unknown");
                let file_num = s.file_num.as_deref().unwrap_or("0");
                let title = format!("{} {} filing by {}", form_type, s.period_of_report.as_deref().unwrap_or(""), entity);

                let mut hasher = Sha256::new();
                hasher.update(format!("edgar_{}_{}", form_type, file_num).as_bytes());
                let id = format!("edgar_{}", hex::encode(&hasher.finalize()[..8]));

                let timestamp = s.file_date.as_deref()
                    .and_then(|d| chrono::NaiveDate::parse_from_str(d, "%Y-%m-%d").ok())
                    .map(|d| d.and_hms_opt(0, 0, 0).unwrap().and_utc())
                    .unwrap_or_else(Utc::now);

                Some(RawRecord {
                    id,
                    source: "sec_edgar".to_string(),
                    source_type: "filing".to_string(),
                    timestamp,
                    title: Some(title.clone()),
                    body: title,
                    url: Some(format!("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum={}", file_num)),
                    metadata: serde_json::json!({
                        "form_type": form_type,
                        "entity_name": entity,
                        "period_of_report": s.period_of_report,
                        "display_names": s.display_names,
                    }),
                })
            })
            .collect();

        Ok(records)
    }
}
