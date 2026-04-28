/**
 * CMATSS 拖轮调度系统 - 语音模块
 * Web Speech API 播报
 */

function initVoice() {
    const btn = document.getElementById('voice-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
        voiceEnabled = !voiceEnabled;
        btn.textContent = voiceEnabled ? '🔊 语音开' : '🔇 语音关';
        if (voiceEnabled) {
            const test = new SpeechSynthesisUtterance('语音播报已开启');
            test.lang = 'zh-CN';
            test.rate = 0.9;
            speechSynthesis.speak(test);
        } else {
            speechSynthesis.cancel();
        }
    });
}

function speakTugAssignment(solution) {
    if (!voiceEnabled || !window.speechSynthesis) return;

    speechSynthesis.cancel();

    const assignments = solution.assignments || [];
    const chainJobs = solution.chain_jobs || [];

    const byJob = {};
    assignments.forEach(a => {
        if (!byJob[a.job_id]) byJob[a.job_id] = [];
        byJob[a.job_id].push(a);
    });

    let idx = 0;
    for (const [jobId, assigns] of Object.entries(byJob)) {
        const tugNames = assigns.map(a => a.tug_name || a.tug_id).join('、');
        const text = `任务 ${jobId}, 指派 ${tugNames} 执行`;
        setTimeout(() => {
            if (!voiceEnabled) return;
            const u = new SpeechSynthesisUtterance(text);
            u.lang = 'zh-CN';
            u.rate = 0.85;
            speechSynthesis.speak(u);
        }, idx * 3000);
        idx++;
    }

    if (chainJobs.length > 0) {
        setTimeout(() => {
            if (!voiceEnabled) return;
            const u = new SpeechSynthesisUtterance(`识别到 ${chainJobs.length} 对连活任务, 预计节省成本`);
            u.lang = 'zh-CN';
            u.rate = 0.85;
            speechSynthesis.speak(u);
        }, idx * 3000 + 1000);
    }
}
