/**
 * Cloudflare Worker: Telegram Bot -> GitHub Actions Serverless Trigger
 * 
 * Free 24/7 cloud relay that receives Telegram commands/button clicks
 * and triggers your GitHub Actions pipeline even when your PC is shutdown!
 */

export default {
  async fetch(request, env) {
    const botToken = getBotToken(env, request);
    const githubToken = getGithubToken(env, request);
    const hasGithubToken = githubToken.length > 5;

    if (request.method !== 'POST') {
      const info = {
        status: "Active",
        message: "Telegram to GitHub Actions Relay is Active!",
        has_TELEGRAM_BOT_TOKEN: !!(botToken && botToken.length > 10),
        has_GITHUB_TOKEN: hasGithubToken,
        token_source: botToken ? (env && (env.TELEGRAM_BOT_TOKEN || env.BOT_TOKEN) ? 'env' : 'url_parameter') : 'missing',
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

    if (!botToken) {
      console.error("TELEGRAM_BOT_TOKEN is missing in Cloudflare Worker environment and URL.");
      return new Response("Missing TELEGRAM_BOT_TOKEN. Configure in Cloudflare Secrets or webhook URL.", { status: 200 });
    }

    try {
      const update = await request.json();
      await handleTelegramUpdate(update, env, botToken, githubToken);
      return new Response('OK', { status: 200 });
    } catch (err) {
      console.error('Error handling update:', err);
      return new Response('Internal Error: ' + err.message, { status: 200 });
    }
  }
};

async function handleTelegramUpdate(update, env, botToken, githubToken = '') {
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
  else if ((cleanLower.includes('analysis') || cleanLower.includes('gemini')) && !cmd.startsWith('/')) cmd = '/analysis';
  else if (cleanLower.includes('evening') && !cmd.startsWith('/')) cmd = '/evening';
  else if (cleanLower.includes('status') && !cmd.startsWith('/')) cmd = '/status';
  else if (cleanLower.includes('news') && !cmd.startsWith('/')) cmd = '/news';
  else if (
    (cleanLower.includes('full pipeline') ||
     cleanLower.includes('full cycle') ||
     cleanLower.includes('start pipeline') ||
     cleanLower.includes('full-cycle') ||
     cleanLower.includes('fullcycle') ||
     cleanLower.includes('full_pipeline') ||
     cleanLower.includes('pipeline')) &&
    !cleanLower.includes('stop') &&
    !cmd.startsWith('/')
  ) {
    cmd = '/full_cycle';
  } else if (cleanLower.includes('stop pipeline') && !cmd.startsWith('/')) {
    cmd = '/stop_pipeline';
  }

  // Normalize commands and aliases to trigger full cycle
  if (
    cmd === '/full_cycle' ||
    cmd === '/full_pipeline' ||
    cmd === '/pipeline' ||
    cmd === '/full-cycle' ||
    cmd === '/fullcycle' ||
    cmd === '/start_pipeline'
  ) {
    cmd = '/full_cycle';
  }

  if (cmd === '/start' || cmd === '/help' || cmd === '/menu') {
    await registerTelegramCommands(botToken);
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
    await triggerGitHubWorkflow(chatId, env, botToken, 'morning', githubToken);
  } else if (cmd === '/analysis' || cmd === '/gemini_analysis' || cmd === '/gemini') {
    await sendTelegramMessage(
      chatId,
      '🧠 *Triggering Gemini AI Deep Stock Analysis in GitHub Actions Cloud!* ☁️\n' +
      '───────────────────────────\n' +
      '• Cloud runner is executing deep market synthesis...\n' +
      '• Gemini 2.5 Flash is analyzing Top 5 stock selection bases & news impact.\n' +
      '• Complete detailed report will arrive here in ~15-30 seconds!\n\n' +
      '💡 *Your computer does NOT need to be on.*',
      botToken
    );
    await triggerGitHubWorkflow(chatId, env, botToken, 'analysis', githubToken);
  } else if (cmd === '/news') {
    await sendTelegramMessage(
      chatId,
      '🌐 *Fetching Live US/Singapore Market Cues & Financial News...* 📰\n' +
      '• Cloud runner is compiling latest headlines...\n' +
      '• Report will arrive shortly.',
      botToken
    );
    await triggerGitHubWorkflow(chatId, env, botToken, 'news', githubToken);
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
    await triggerGitHubWorkflow(chatId, env, botToken, 'evening', githubToken);
  } else if (cmd === '/full_cycle') {
    await sendTelegramMessage(
      chatId,
      '🔄 *Triggering Full Pipeline (Full Cycle) in GitHub Actions Cloud!* ☁️\n' +
      '───────────────────────────\n' +
      '• GitHub Actions runner is spinning up...\n' +
      '• 🌅 *Phase 1:* Morning Prediction (< ₹500 stocks, Gemini AI + News)\n' +
      '• ⏱️ *Phase 2:* 1-Minute Live Intraday Tracking (until 03:30 PM IST)\n' +
      '• 🌆 *Phase 3:* Evening P&L Report & Retraining (after market close)\n\n' +
      '💡 *Your computer does NOT need to be on.* Reports will arrive directly in this chat!',
      botToken
    );
    await triggerGitHubWorkflow(chatId, env, botToken, 'full-cycle', githubToken);
  } else if (cmd === '/stop_pipeline') {
    await sendTelegramMessage(
      chatId,
      '⏸️ *Pipeline Management:*\n' +
      '• Cloud scheduled runs trigger automatically at 09:15 AM and 04:30 PM IST (Mon-Fri).\n' +
      '• On-demand jobs run whenever you trigger `/morning`, `/evening`, or `/full_pipeline`.\n' +
      '• To cancel any active cloud run, visit GitHub ➔ Actions ➔ Select Run ➔ Cancel.',
      botToken
    );
  } else if (cmd === '/status') {
    await checkGitHubActionsStatus(chatId, env, botToken, githubToken);
  } else {
    await sendFallbackMenu(chatId, text, env, botToken);
  }
}

async function registerTelegramCommands(botToken) {
  if (!botToken) return;
  const commands = [
    { command: "morning", description: "🌅 Run Morning Prediction (< ₹500)" },
    { command: "full_pipeline", description: "🔄 Run Full Pipeline Cycle (Morning + Monitor + Evening)" },
    { command: "evening", description: "🌆 Run Evening P&L Report & Retraining" },
    { command: "status", description: "📊 Check Pipeline Status on GitHub Cloud" },
    { command: "menu", description: "🎛️ Open Control Panel with Clickable Buttons" },
    { command: "help", description: "❓ Show Help & Commands Guide" }
  ];
  try {
    await fetch(`https://api.telegram.org/bot${botToken}/setMyCommands`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commands })
    });
  } catch (e) {}
}

function getBotToken(env, request) {
  if (env) {
    const fromEnv = (
      env.TELEGRAM_BOT_TOKEN ||
      env.telegram_bot_token ||
      env.BOT_TOKEN ||
      env.bot_token ||
      env.TELEGRAM_TOKEN ||
      env.telegram_token ||
      env.TG_BOT_TOKEN ||
      env.TG_TOKEN ||
      ''
    ).trim();
    if (fromEnv && fromEnv.length > 10) return fromEnv;
  }
  if (request && request.url) {
    try {
      const url = new URL(request.url);
      const queryToken = (
        url.searchParams.get('token') ||
        url.searchParams.get('bot_token') ||
        url.searchParams.get('telegram_bot_token') ||
        ''
      ).trim();
      if (queryToken && queryToken.length > 10) return queryToken;

      const pathParts = url.pathname.replace(/^\/+/, '').split('/');
      if (pathParts[0]) {
        const first = pathParts[0].replace(/^bot/, '');
        if (first.includes(':') && first.length > 10) return first;
      }
    } catch (e) {}
  }
  return '';
}

function getGithubToken(env, request) {
  if (env) {
    const fromEnv = (
      env.GITHUB_TOKEN ||
      env.github_token ||
      env.GH_TOKEN ||
      env.gh_token ||
      env.GITHUB_PAT ||
      env.PAT_TOKEN ||
      env.TOKEN ||
      ''
    ).trim();
    if (fromEnv && fromEnv.length > 5) return fromEnv;
  }
  if (request && request.url) {
    try {
      const url = new URL(request.url);
      const queryGh = (
        url.searchParams.get('gh_token') ||
        url.searchParams.get('github_token') ||
        ''
      ).trim();
      if (queryGh && queryGh.length > 5) return queryGh;
    } catch (e) {}
  }
  return '';
}

async function triggerGitHubWorkflow(chatId, env, botToken, mode, githubToken = '') {
  const ghToken = (githubToken || getGithubToken(env)).trim();

  if (!ghToken) {
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
        'Authorization': `Bearer ${ghToken}`,
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

async function checkGitHubActionsStatus(chatId, env, botToken, githubToken = '') {
  const ghToken = (githubToken || getGithubToken(env)).trim();
  const owner = env.GITHUB_OWNER || 'JagadeeshVedula';
  const repo = env.GITHUB_REPO || 'TradePrediction';

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/runs?per_page=3`;

  try {
    const headers = {
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'Cloudflare-Telegram-Relay'
    };
    if (ghToken) {
      headers['Authorization'] = `Bearer ${ghToken}`;
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
    '• 🔄 *Full Pipeline (Full Cycle)*: Complete Morning + Intraday Tracking + Evening Report\n' +
    '• 🧠 *Gemini AI Analysis*: Detailed selection bases, technical rationale & news impact for Top 5 stocks\n' +
    '• 🌆 *Evening Report*: Post-market close P&L breakdown\n' +
    '• 📊 *Pipeline Status*: Check GitHub Actions cloud runner status\n' +
    '• 🌐 *Market News*: Live US & Singapore cues + Moneycontrol/TOI headlines\n' +
    '───────────────────────────\n' +
    '💡 *Tap any button below to trigger GitHub Actions immediately!*';

  const inlineKeyboard = {
    inline_keyboard: [
      [
        { text: '🌅 Morning Prediction', callback_data: '/morning' },
        { text: '🔄 Full Pipeline', callback_data: '/full_cycle' }
      ],
      [
        { text: '🧠 Gemini AI Analysis', callback_data: '/analysis' },
        { text: '🌐 Global News & Cues', callback_data: '/news' }
      ],
      [
        { text: '🌆 Evening P&L Report', callback_data: '/evening' },
        { text: '📊 Pipeline Status', callback_data: '/status' }
      ]
    ]
  };

  const replyKeyboard = {
    keyboard: [
      [{ text: '🌅 Morning Prediction' }, { text: '🔄 Full Pipeline' }],
      [{ text: '🧠 Gemini Analysis' }, { text: '🌐 Market News' }],
      [{ text: '🌆 Evening Report' }, { text: '📊 Status' }],
      [{ text: '🎛️ Menu' }]
    ],
    resize_keyboard: true,
    is_persistent: true
  };

  await sendTelegramMessage(chatId, panelText, botToken, inlineKeyboard);
  await sendTelegramMessage(chatId, '👇 *Control buttons are also docked on your keyboard below:*', botToken, replyKeyboard);
}

async function sendFallbackMenu(chatId, receivedText, env, botToken) {
  const msg = 
    `🤖 *Received:* \`${receivedText}\`\n\n` +
    'Tap any action below to execute in GitHub Actions Cloud:\n' +
    '• 🌅 `/morning` — Run Morning Prediction (< ₹500)\n' +
    '• 🧠 `/analysis` — Gemini AI Stock Selection & News Analysis\n' +
    '• 🔄 `/full_pipeline` — Full Pipeline (Morning + Intraday + Evening Cycle)\n' +
    '• 🌆 `/evening` — Evening P&L & Retraining\n' +
    '• 📊 `/status` — View GitHub Pipeline Runs\n' +
    '• 🌐 `/news` — US & Singapore Cues + News';

  const inlineKeyboard = {
    inline_keyboard: [
      [
        { text: '🌅 Morning Prediction', callback_data: '/morning' },
        { text: '🔄 Full Pipeline', callback_data: '/full_cycle' }
      ],
      [
        { text: '🧠 Gemini AI Analysis', callback_data: '/analysis' },
        { text: '🌐 Global News & Cues', callback_data: '/news' }
      ],
      [
        { text: '🌆 Evening P&L Report', callback_data: '/evening' },
        { text: '📊 Pipeline Status', callback_data: '/status' }
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
