/**
 * Cloudflare Worker: Telegram Bot -> GitHub Actions Serverless Trigger
 * 
 * Free 24/7 cloud relay that receives Telegram commands/button clicks
 * and triggers your GitHub Actions pipeline even when your PC is shutdown!
 */

export default {
  async fetch(request, env) {
    const botToken = (env.TELEGRAM_BOT_TOKEN || "").trim();
    const githubToken = getGithubToken(env);
    const hasGithubToken = githubToken.length > 5;

    if (request.method !== 'POST') {
      const info = {
        status: "Active",
        message: "Telegram to GitHub Actions Relay is Active!",
        has_TELEGRAM_BOT_TOKEN: !!(botToken && botToken.length > 10),
        has_GITHUB_TOKEN: hasGithubToken,
        configured_env_keys: Object.keys(env || {}).filter(k => !k.startsWith('__')),
        github_owner: env.GITHUB_OWNER || "JagadeeshVedula",
        github_repo: env.GITHUB_REPO || "TradePrediction",
        github_workflow: env.GITHUB_WORKFLOW || "stock_scheduler.yml"
      };
      return new Response(JSON.stringify(info, null, 2), {
        status: 200,
        headers: { "Content-Type": "application/json" }
      });
    }

    try {
      const update = await request.json();
      await handleTelegramUpdate(update, env, botToken);
      return new Response('OK', { status: 200 });
    } catch (err) {
      console.error('Error handling update:', err);
      return new Response('Internal Error: ' + err.message, { status: 200 });
    }
  }
};

async function handleTelegramUpdate(update, env, botToken) {
  let chatId = null;
  let text = '';
  let callbackQueryId = null;

  if (update.message) {
    chatId = update.message.chat.id;
    text = (update.message.text || '').trim();
  } else if (update.callback_query) {
    callbackQueryId = update.callback_query.id;
    chatId = update.callback_query.message.chat.id;
    text = (update.callback_query.data || '').trim();

    if (callbackQueryId) {
      try {
        await fetch(`https://api.telegram.org/bot${botToken}/answerCallbackQuery`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ callback_query_id: callbackQueryId, text: 'Executing...' })
        });
      } catch (e) {}
    }
  }

  if (!chatId) return;

  const cleanLower = text.toLowerCase();

  let cmd = text.split(' ')[0].toLowerCase().split('@')[0];
  if (cleanLower.includes('morning') && !cmd.startsWith('/')) cmd = '/morning';
  else if (cleanLower.includes('evening') && !cmd.startsWith('/')) cmd = '/evening';
  else if (cleanLower.includes('status') && !cmd.startsWith('/')) cmd = '/status';
  else if (cleanLower.includes('news') && !cmd.startsWith('/')) cmd = '/news';
  else if (cleanLower.includes('start pipeline') && !cmd.startsWith('/')) cmd = '/start_pipeline';
  else if (cleanLower.includes('stop pipeline') && !cmd.startsWith('/')) cmd = '/stop_pipeline';

  if (cmd === '/start' || cmd === '/help' || cmd === '/menu') {
    await sendControlPanel(chatId, env, botToken);
  } else if (cmd === '/morning') {
    await sendTelegramMessage(
      chatId,
      '🚀 *Triggering Morning Prediction in GitHub Actions Cloud!* ☁️\n' +
      '───────────────────────────\n' +
      '• GitHub Actions runner is spinning up...\n' +
      '• Gemini AI will evaluate Top 5 Indian stocks (< ₹500).\n' +
      '• Full report will arrive directly in this chat in ~1-2 minutes!\n\n' +
      '💡 *Your computer does NOT need to be on.*',
      botToken
    );
    await triggerGitHubWorkflow(chatId, env, botToken, 'morning');
  } else if (cmd === '/evening') {
    await sendTelegramMessage(
      chatId,
      '🌆 *Triggering Evening P&L Report in GitHub Actions Cloud!* ☁️\n' +
      '───────────────────────────\n' +
      '• GitHub Actions runner is executing post-close analysis...\n' +
      '• Intraday P&L (+₹2 / -₹1) and retraining will be processed.\n' +
      '• Report will arrive here shortly.',
      botToken
    );
    await triggerGitHubWorkflow(chatId, env, botToken, 'evening');
  } else if (cmd === '/full_cycle') {
    await sendTelegramMessage(
      chatId,
      '🔄 *Triggering Full Market Cycle in GitHub Actions!* ☁️\n' +
      'Morning Prediction + 1-minute monitoring until 3:30 PM + Evening Report.',
      botToken
    );
    await triggerGitHubWorkflow(chatId, env, botToken, 'full-cycle');
  } else if (cmd === '/status') {
    await checkGitHubActionsStatus(chatId, env, botToken);
  } else {
    await sendFallbackMenu(chatId, text, env, botToken);
  }
}

function getGithubToken(env) {
  if (!env) return '';
  return (
    env.GITHUB_TOKEN ||
    env.github_token ||
    env.GH_TOKEN ||
    env.gh_token ||
    env.GITHUB_PAT ||
    env.PAT_TOKEN ||
    env.TOKEN ||
    ''
  ).trim();
}

async function triggerGitHubWorkflow(chatId, env, botToken, mode) {
  const githubToken = getGithubToken(env);

  if (!githubToken) {
    await sendTelegramMessage(
      chatId,
      '⚠️ *GITHUB_TOKEN is missing in Cloudflare Secrets!*\n\n' +
      'To fix this:\n' +
      '1. Open Cloudflare Dashboard ➔ Workers ➔ `tradeprediction` ➔ **Settings** ➔ **Variables and Secrets**.\n' +
      '2. Add variable name: `GITHUB_TOKEN`\n' +
      '3. Value: Your GitHub Personal Access Token (classic with `repo` and `workflow` checked).\n' +
      '4. Click Deploy / Save.',
      botToken
    );
    return false;
  }

  const owner = env.GITHUB_OWNER || 'JagadeeshVedula';
  const repo = env.GITHUB_REPO || 'TradePrediction';
  const workflow = env.GITHUB_WORKFLOW || 'stock_scheduler.yml';

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${githubToken}`,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Cloudflare-Telegram-Relay',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: { mode: mode }
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`GitHub API error (${response.status}):`, errorText);
      await sendTelegramMessage(
        chatId,
        `❌ *GitHub Actions Trigger Error (HTTP ${response.status})*\n` +
        `Response: \`${errorText.slice(0, 200)}\`\n\n` +
        `💡 Ensure your \`GITHUB_TOKEN\` in Cloudflare has \`repo\` and \`workflow\` scope enabled.`,
        botToken
      );
      return false;
    }

    await sendTelegramMessage(
      chatId,
      `✅ *GitHub Actions Workflow Dispatched Successfully!* 🚀\n` +
      `• *Mode:* \`${mode}\`\n` +
      `• *Workflow:* \`${workflow}\`\n` +
      `• *Cloud Runner:* Started\n\n` +
      `Your stock report will be delivered here once processing completes (~1-2 mins).`,
      botToken
    );
    return true;
  } catch (err) {
    await sendTelegramMessage(chatId, `❌ Network error contacting GitHub: ${err.message}`, botToken);
    return false;
  }
}

async function checkGitHubActionsStatus(chatId, env, botToken) {
  const githubToken = (env.GITHUB_TOKEN || '').trim();
  const owner = env.GITHUB_OWNER || 'JagadeeshVedula';
  const repo = env.GITHUB_REPO || 'TradePrediction';

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/runs?per_page=3`;

  try {
    const headers = {
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'Cloudflare-Telegram-Relay'
    };
    if (githubToken) {
      headers['Authorization'] = `Bearer ${githubToken}`;
    }

    const res = await fetch(url, { headers });

    if (!res.ok) {
      await sendTelegramMessage(chatId, '⚠️ Could not fetch GitHub Actions status. Check GITHUB_TOKEN.', botToken);
      return;
    }

    const data = await res.json();
    const runs = data.workflow_runs || [];

    if (runs.length === 0) {
      await sendTelegramMessage(chatId, '📊 *GitHub Actions:* No recent workflow runs found.', botToken);
      return;
    }

    let msg = '📊 *RECENT GITHUB ACTIONS PIPELINE RUNS* ☁️\n───────────────────────────\n';
    for (const r of runs.slice(0, 3)) {
      const icon = r.status === 'completed' 
        ? (r.conclusion === 'success' ? '✅' : '❌') 
        : (r.status === 'in_progress' ? '🔄 RUNNING' : '⏳ QUEUED');
      msg += `• *Run #${r.run_number}*: ${icon} ${r.status.toUpperCase()}\n`;
      msg += `  Trigger: \`${r.event}\` | Created: ${new Date(r.created_at).toLocaleTimeString('en-US', { timeZone: 'Asia/Kolkata' })} IST\n`;
    }
    msg += '───────────────────────────\n💡 Send `/morning` to run predictions in GitHub cloud anytime!';
    await sendTelegramMessage(chatId, msg, botToken);
  } catch (e) {
    await sendTelegramMessage(chatId, `❌ Error fetching pipeline status: ${e.message}`, botToken);
  }
}

async function sendControlPanel(chatId, env, botToken) {
  const panelText = 
    '🎛️ *INDIAN STOCK AI CLOUD CONTROL PANEL* 🚀\n' +
    '───────────────────────────\n' +
    'Operate your cloud trading pipeline directly from Telegram (No PC needed):\n\n' +
    '• 🌅 *Run Morning Prediction*: Triggers Gemini AI & Global News pipeline in GitHub Actions\n' +
    '• 📊 *Pipeline Status*: Check GitHub Actions cloud runner status\n' +
    '• 🌆 *Evening Report*: Post-market close P&L breakdown\n' +
    '• 🔄 *Full Day Cycle*: Complete morning + intraday tracking session\n' +
    '───────────────────────────\n' +
    '💡 *Tap any button below to trigger GitHub Actions immediately!*';

  const inlineKeyboard = {
    inline_keyboard: [
      [
        { text: '🌅 Run Morning Prediction', callback_data: '/morning' },
        { text: '📊 Pipeline Status', callback_data: '/status' }
      ],
      [
        { text: '🌆 Evening P&L Report', callback_data: '/evening' },
        { text: '🔄 Full Day Cycle', callback_data: '/full_cycle' }
      ]
    ]
  };

  await sendTelegramMessage(chatId, panelText, botToken, inlineKeyboard);
}

async function sendFallbackMenu(chatId, receivedText, env, botToken) {
  const msg = 
    `🤖 *Received:* \`${receivedText}\`\n\n` +
    'Tap any action below to execute in GitHub Actions Cloud:\n' +
    '• 🌅 `/morning` — Run Morning Prediction (< ₹500)\n' +
    '• 📊 `/status` — View GitHub Pipeline Runs\n' +
    '• 🌆 `/evening` — Evening P&L & Retraining\n' +
    '• 🔄 `/full_cycle` — Full Intraday Session';

  const inlineKeyboard = {
    inline_keyboard: [
      [
        { text: '🌅 Run Morning Prediction', callback_data: '/morning' },
        { text: '📊 Pipeline Status', callback_data: '/status' }
      ],
      [
        { text: '🌆 Evening P&L Report', callback_data: '/evening' }
      ]
    ]
  };

  await sendTelegramMessage(chatId, msg, botToken, inlineKeyboard);
}

async function sendTelegramMessage(chatId, text, botToken, replyMarkup = null) {
  const payload = {
    chat_id: chatId,
    text: text,
    parse_mode: 'Markdown'
  };
  if (replyMarkup) payload.reply_markup = replyMarkup;

  try {
    const res = await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      delete payload.parse_mode;
      await fetch(`https://api.telegram.org/bot${botToken}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
    }
  } catch (e) {
    console.error('Error sending telegram message:', e);
  }
}
