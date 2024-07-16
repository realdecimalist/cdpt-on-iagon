import express from 'express';
import fetch from 'node-fetch';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import FormData from 'form-data';
import { marked } from 'marked';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const WHITELISTED_USER_IDS = ['410954739547766795', '780451451100200971', '824443775928762368'];

app.use(cors());
app.use(express.json());

app.use(express.static(path.join(__dirname, '../dist')));

const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;
const IAGON_API_KEY = process.env.IAGON_API_KEY;
const IAGON_PASSWORD = process.env.IAGON_PASSWORD;
const MAESTRO_API_KEY = process.env.MAESTRO_API_KEY;

app.get('/config', (req, res) => {
  res.json({ clientId: CLIENT_ID });
  console.log('Sent config:', { clientId: CLIENT_ID });
});

app.post('/discord/token', async (req, res) => {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    grant_type: 'authorization_code',
    code: req.body.code,
    redirect_uri: 'https://fancy-pond-7060.iagon.io',
  });

  console.log('Requesting token with params:', params.toString());

  try {
    const tokenResponse = await fetch('https://discord.com/api/oauth2/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: params
    });

    const tokenData = await tokenResponse.json();
    console.log('Token response:', tokenData);

    if (!tokenResponse.ok) {
      console.error('Token request failed:', tokenData);
      return res.status(tokenResponse.status).json(tokenData);
    }

    // Fetch user info to get the user ID
    const userResponse = await fetch('https://discord.com/api/users/@me', {
      headers: {
        'Authorization': `Bearer ${tokenData.access_token}`
      }
    });

    const userData = await userResponse.json();
    console.log('User data:', userData);

    if (WHITELISTED_USER_IDS.includes(userData.id)) {
      // If User is whitelisted, allow direct access
      return res.json(tokenData);
    }

    // Proceed with the entitlements flow if not whitelisted
    res.json(tokenData);
  } catch (error) {
    console.error('Failed to fetch token:', error);
    res.status(500).json({ error: 'Failed to fetch token' });
  }
});

app.get('/discord/entitlements', async (req, res) => {
  const { accessToken, user_id, sku_ids, before, after, limit, guild_id, exclude_ended } = req.query;

  const queryParams = new URLSearchParams();
  if (user_id) queryParams.append('user_id', user_id);
  if (sku_ids) queryParams.append('sku_ids', sku_ids);
  if (before) queryParams.append('before', before);
  if (after) queryParams.append('after', after);
  if (limit) queryParams.append('limit', limit);
  if (guild_id) queryParams.append('guild_id', guild_id);
  if (exclude_ended) queryParams.append('exclude_ended', exclude_ended);

  console.log('Requesting entitlements with access token:', accessToken);

  try {
    const entitlementsResponse = await fetch(`https://discord.com/api/v10/applications/${CLIENT_ID}/entitlements?${queryParams.toString()}`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    });

    const entitlements = await entitlementsResponse.json();
    console.log('Entitlements response:', entitlements);

    if (!entitlementsResponse.ok) {
      console.error('Entitlements request failed:', entitlements);
      return res.status(entitlementsResponse.status).json(entitlements);
    }

    res.json(entitlements);
  } catch (error) {
    console.error('Failed to fetch entitlements:', error);
    res.status(500).json({ error: 'Failed to fetch entitlements' });
  }
});

app.post('/save-chat', async (req, res) => {
  try {
    const { discordId, chatHistory } = req.body;

    if (!discordId || !chatHistory) {
      return res.status(400).json({ error: 'discordId and chatHistory are required' });
    }

    const formData = new FormData();
    formData.append('file', Buffer.from(JSON.stringify(chatHistory)), `${discordId}_chatHistory.json`);
    formData.append('filename', `${discordId}_chatHistory.json`);
    formData.append('visibility', 'public');

    console.log('Saving chat history for Discord ID:', discordId);

    const response = await fetch('https://gw.iagon.com/api/v2/storage/upload', {
      method: 'POST',
      headers: {
        'x-api-key': IAGON_API_KEY
      },
      body: formData
    });

    const data = await response.json();
    if (!response.ok) {
      console.error('Failed to save chat history:', data);
      return res.status(response.status).json(data);
    }

    console.log('Chat history saved:', data);
    res.json(data);
  } catch (error) {
    console.error('Error saving chat history:', error);
    res.status(500).json({ error: 'Failed to save chat history' });
  }
});

app.get('/load-chat', async (req, res) => {
    try {
        const { fileId } = req.query;
        if (!fileId) {
            console.error('Error: fileId is required');
            return res.status(400).json({ error: 'fileId is required' });
        }

        console.log('Loading chat history with file ID:', fileId);

        // Fetch the list of files
        const listResponse = await fetch('https://gw.iagon.com/api/v2/storage/directory?visibility=public', {
            method: 'GET',
            headers: {
                'x-api-key': IAGON_API_KEY,
                'Authorization': `Bearer ${IAGON_API_KEY}`
            }
        });

        if (!listResponse.ok) {
            const errorData = await listResponse.json();
            console.error('Failed to fetch file list:', errorData);
            return res.status(listResponse.status).json(errorData);
        }

        const listData = await listResponse.json();
        const files = listData.data.files;

        // Identify the most recent file
        const mostRecentFile = files.reduce((latest, file) => {
            return new Date(file.updated_at) > new Date(latest.updated_at) ? file : latest;
        });

        console.log('Most recent file ID:', mostRecentFile._id);

        // Fetch the most recent file
        const response = await fetch(`https://gw.iagon.com/api/v2/storage/file/${mostRecentFile._id}/download`, {
            method: 'GET',
            headers: {
                'x-api-key': IAGON_API_KEY,
                'Authorization': `Bearer ${IAGON_API_KEY}`,
                'x-password': IAGON_PASSWORD
            }
        });

        if (!response.ok) {
            const errorData = await response.text(); // Log the raw response text
            console.error('Failed to load chat history:', errorData);
            return res.status(response.status).json({ error: errorData });
        }

        const rawData = await response.text(); // Get the raw response text
        console.log('Raw response data:', rawData);

        let data;
        try {
            data = JSON.parse(rawData); // Attempt to parse the raw response as JSON
            console.log('Parsed data:', data);
        } catch (parseError) {
            console.error('Error parsing JSON:', parseError);
            return res.status(500).json({ error: 'Failed to parse chat history' });
        }

        // Directly return the parsed data
        res.json(data);
    } catch (error) {
        console.error('Error loading chat history:', error);
        res.status(500).json({ error: 'Failed to load chat history' });
    }
});



app.post('/process-markdown', (req, res) => {
  const { markdownText } = req.body;
  const htmlContent = marked(markdownText);
  res.json({ htmlContent });
});

app.get('/get-market-price', async (req, res) => {
    const { currency } = req.query;

    if (!currency) {
        return res.status(400).json({ error: 'Currency is required' });
    }

    const url = `https://mainnet.gomaestro-api.org/v1/markets/dexs/stats/minswap/${currency}-IAG`;
    const headers = {
        'Accept': 'application/json',
        'api-key': MAESTRO_API_KEY
    };

    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: headers
        });

        const data = await response.json();

        console.log('Response Data:', data);
        if (!response.ok) {
            console.error(`Failed to fetch ${currency} price:`, data);
            return res.status(response.status).json(data);
        }

        // Extract the price from the response data
        const price = data['latest_price']?.['coin_a_latest_price'] || 'Price not found';
        res.json({ price: price });
    } catch (error) {
        console.error(`Error fetching ${currency} price:`, error);
        res.status(500).json({ error: `Failed to fetch ${currency} price` });
    }
});

app.get('/get-current-epoch-details', async (req, res) => {
    try {
      const response = await fetch('https://mainnet.gomaestro-api.org/v1/epochs/current', {
        headers: {
          'Accept': 'application/json',
          'api-key': MAESTRO_API_KEY
        }
      });
  
      if (!response.ok) {
        const errorData = await response.json();
        console.error('Failed to fetch current epoch details:', errorData);
        return res.status(response.status).json(errorData);
      }
  
      const data = await response.json();
      res.json(data);
    } catch (error) {
      console.error('Error fetching current epoch details:', error);
      res.status(500).json({ error: 'Failed to fetch current epoch details' });
    }
  });

app.listen(port, () => {
  console.log(`Server running at https://localhost:${port}`);
});
