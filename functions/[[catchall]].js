/**
 * Cloudflare Pages Function (Catch-all router):
 * Handles requests for Cloudflare Pages deployments
 */

export async function onRequest(context) {
  const { request, env } = context;

  if (request.method !== 'POST') {
    return context.next();
  }

  try {
    const update = await request.json();
    await handleTelegramUpdate(update, env);
    return new Response('OK', { status: 200 });
  } catch (err) {
    console.error('Error handling update:', err);
    return new Response('Internal Error: ' + err.message, { status: 200 });
  }
}

async function handleTelegramUpdate(update, env) {
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
      await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ callback_query_id: callbackQueryId, text: 'Triggering...' })
      });
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
    await sendControlPanel(chatId, env);
  } else if (cmd === '/morning') {
    await sendTelegramMessage(
      chatId,
      '🚀 *Triggering Morning Prediction in GitHub Actions Cloud!* ☁️\n' +
      '───────────────────────────\n' +
      '• GitHub Actions runner is spinning up...\n' +
      '• Gemini AI will evaluate Top 5 Indian stocks (< ₹500).\n' +
      '• Full report will arrive directly in this chat in ~1-2 minutes!\n\n' +
      '💡 *Your computer does NOT need to be on.*',
      env
    );
    await triggerGitHubWorkflow(env, 'morning');
  } else if (cmd === '/evening') {
    await sendTelegramMessage(
      chatId,
      '🌆 *Triggering Evening P&L Report in GitHub Actions Cloud!* ☁️\n' +
      '───────────────────────────\n' +
      '• GitHub Actions runner is executing post-close analysis...\n' +
      '• Intraday P&L (+₹2 / -₹1) and retraining will be processed.\n' +
      '• Report will arrive here shortly.',
      env
    );
    await triggerGitHubWorkflow(env, 'evening');
  } else if (cmd === '/full_cycle') {
    await sendTelegramMessage(
      chatId,
      '🔄 *Triggering Full Market Cycle in GitHub Actions!* ☁️\n' +
      'Morning Prediction + 1-minute monitoring until 3:30 PM + Evening Report.',
      env
    );
    await triggerGitHubWorkflow(env, 'full-cycle');
  } else if (cmd === '/status') {
    await checkGitHubActionsStatus(chatId, env);
  } else {
    await sendFallbackMenu(chatId, text, env);
  }
}

async function triggerGitHubWorkflow(env, mode) {
  const owner = env.GITHUB_OWNER || 'JagadeeshVedula';
  const repo = env.GITHUB_REPO || 'TradePrediction';
  const workflow = env.GITHUB_WORKFLOW || 'stock_scheduler.yml';

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`;

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'Cloudflare-Telegram-Relay',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      ref: 'main',
      inputs: { mode: mode }
    })
  });

  return response.ok;
}

async function checkGitHubActionsStatus(chatId, env) {
  const owner = env.GITHUB_OWNER || 'JagadeeshVedula';
  const repo = env.GITHUB_REPO || 'TradePrediction';

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/runs?per_page=3`;

  try {
    const res = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${env.GITHUB_TOKEN}`,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'Cloudflare-Telegram-Relay'
      }
    });

    if (!res.ok) {
      await sendTelegramMessage(chatId, '⚠️ Could not fetch GitHub Actions status. Check GITHUB_TOKEN.', env);
      return;
    }

    const data = await res.json();
    const runs = data.workflow_runs || [];

    if (runs.length === 0) {
      await sendTelegramMessage(chatId, '📊 *GitHub Actions:* No recent workflow runs found.', env);
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
    await sendTelegramMessage(chatId, msg, env);
  } catch (e) {
    await sendTelegramMessage(chatId, `❌ Error fetching pipeline status: ${e.message}`, env);
  }
}

async function sendControlPanel(chatId, env) {
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

  await sendTelegramMessage(chatId, panelText, env, inlineKeyboard);
}

async function sendFallbackMenu(chatId, receivedText, env) {
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

  await sendTelegramMessage(chatId, msg, env, inlineKeyboard);
}

async function sendTelegramMessage(chatId, text, env, replyMarkup = null) {
  const payload = {
    chat_id: chatId,
    text: text,
    parse_mode: 'Markdown'
  };
  if (replyMarkup) payload.reply_markup = replyMarkup;

  await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
}
