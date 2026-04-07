use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::Deserialize;
use sha2::{Digest, Sha256};
use tracing::info;

use super::RawRecord;

pub struct RedditSource {
    client: Client,
    subreddits: Vec<String>,
    post_limit: usize,
    access_token: String,
}

#[derive(Debug, Deserialize)]
struct RedditTokenResponse {
    access_token: String,
}

#[derive(Debug, Deserialize)]
struct RedditListing {
    data: RedditListingData,
}

#[derive(Debug, Deserialize)]
struct RedditListingData {
    children: Vec<RedditChild>,
}

#[derive(Debug, Deserialize)]
struct RedditChild {
    data: RedditPost,
}

#[derive(Debug, Deserialize)]
struct RedditPost {
    id: String,
    title: String,
    selftext: Option<String>,
    score: i64,
    num_comments: i64,
    created_utc: f64,
    subreddit: String,
    url: String,
    upvote_ratio: Option<f64>,
}

impl RedditSource {
    pub fn from_env() -> Result<Self> {
        let client_id = std::env::var("REDDIT_CLIENT_ID").context("REDDIT_CLIENT_ID not set")?;
        let client_secret = std::env::var("REDDIT_CLIENT_SECRET").context("REDDIT_CLIENT_SECRET not set")?;
        let user_agent = std::env::var("REDDIT_USER_AGENT")
            .unwrap_or_else(|_| "lumina-research/0.1".to_string());
        let subreddits = std::env::var("REDDIT_SUBREDDITS")
            .unwrap_or_else(|_| "investing,MacroEconomics,Economics".to_string())
            .split(',')
            .map(|s| s.trim().to_string())
            .collect();
        let post_limit = std::env::var("REDDIT_POST_LIMIT")
            .unwrap_or_else(|_| "100".to_string())
            .parse::<usize>()
            .unwrap_or(100);

        let client = Client::builder()
            .user_agent(&user_agent)
            .timeout(std::time::Duration::from_secs(30))
            .build()?;

        let rt = tokio::runtime::Handle::current();
        let access_token = rt.block_on(Self::authenticate(&client, &client_id, &client_secret, &user_agent))?;

        Ok(Self { client, subreddits, post_limit, access_token })
    }

    async fn authenticate(client: &Client, id: &str, secret: &str, user_agent: &str) -> Result<String> {
        let resp = client
            .post("https://www.reddit.com/api/v1/access_token")
            .basic_auth(id, Some(secret))
            .header("User-Agent", user_agent)
            .form(&[("grant_type", "client_credentials")])
            .send()
            .await
            .context("Reddit auth request failed")?;

        let token: RedditTokenResponse = resp.json().await.context("Reddit auth JSON failed")?;
        Ok(token.access_token)
    }

    pub async fn fetch(&self) -> Result<Vec<RawRecord>> {
        let mut all_records = Vec::new();

        for sub in &self.subreddits {
            info!("Reddit fetching r/{}", sub);
            for sort in &["hot", "top"] {
                match self.fetch_subreddit(sub, sort).await {
                    Ok(records) => all_records.extend(records),
                    Err(e) => tracing::warn!("Reddit r/{} ({}) failed: {}", sub, sort, e),
                }
                tokio::time::sleep(std::time::Duration::from_millis(600)).await;
            }
        }

        all_records.dedup_by_key(|r| r.id.clone());
        Ok(all_records)
    }

    async fn fetch_subreddit(&self, subreddit: &str, sort: &str) -> Result<Vec<RawRecord>> {
        let limit = self.post_limit.min(100);
        let url = format!(
            "https://oauth.reddit.com/r/{}/{}?limit={}",
            subreddit, sort, limit
        );

        let resp = self.client
            .get(&url)
            .bearer_auth(&self.access_token)
            .send()
            .await
            .context("Reddit listing request failed")?;

        let listing: RedditListing = resp.json().await.context("Reddit listing JSON failed")?;

        let records = listing.data.children
            .into_iter()
            .filter_map(|child| {
                let post = child.data;
                let text = match &post.selftext {
                    Some(t) if !t.is_empty() && t != "[removed]" && t != "[deleted]" => {
                        format!("{}\n\n{}", post.title, t)
                    }
                    _ => post.title.clone(),
                };

                if text.len() < 20 {
                    return None;
                }

                let mut hasher = Sha256::new();
                hasher.update(format!("reddit_{}", post.id).as_bytes());
                let id = format!("reddit_{}", hex::encode(&hasher.finalize()[..8]));

                let timestamp = DateTime::<Utc>::from_timestamp(post.created_utc as i64, 0)
                    .unwrap_or_else(Utc::now);

                Some(RawRecord {
                    id,
                    source: format!("reddit/r/{}", post.subreddit),
                    source_type: "social".to_string(),
                    timestamp,
                    title: Some(post.title),
                    body: text,
                    url: Some(format!("https://reddit.com{}", post.url)),
                    metadata: serde_json::json!({
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "upvote_ratio": post.upvote_ratio,
                        "subreddit": post.subreddit,
                        "sort": sort,
                    }),
                })
            })
            .collect();

        Ok(records)
    }
}
