import express from 'express';
import fetch from 'node-fetch';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

dotenv.config();

const app = express();
const port = process.env.PORT || 3000;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

app.use(cors());
app.use(express.json());

// Serve static files from the dist directory
app.use(express.static(path.join(__dirname, '../dist')));

const CLIENT_ID = process.env.CLIENT_ID;
const CLIENT_SECRET = process.env.CLIENT_SECRET;

app.get('/config', (req, res) => {
    res.json({
        clientId: CLIENT_ID
    });
});

app.post('/discord/token', async (req, res) => {
    const params = new URLSearchParams({
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        grant_type: 'authorization_code',
        code: req.body.code,
        redirect_uri: 'http://shrill-queen-0263.iagon.io/',
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

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
