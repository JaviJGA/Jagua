let taskId = new URLSearchParams(window.location.search).get('task_id');
let checkInterval;

function updateProgressBar(progress) {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    if (fill) fill.style.width = progress + '%';
    if (text) text.textContent = progress + '% completado';
}

function updateTaskStatus(data) {
    updateProgressBar(data.progress);
    
    const statusMessage = document.getElementById('status-message');
    if (statusMessage) statusMessage.textContent = data.message || '';
    
    const currentUrl = document.getElementById('current-url');
    const currentUrlContainer = document.getElementById('current-url-container');
    
    if (data.current_url && currentUrl && currentUrlContainer) {
        currentUrl.textContent = data.current_url;
        currentUrlContainer.style.display = 'block';
    } else if (currentUrlContainer) {
        currentUrlContainer.style.display = 'none';
    }
    
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = data.status !== 'completed' ? 'block' : 'none';
    }

    if (data.status === 'completed') {
        clearInterval(checkInterval);
        const resultsBtn = document.getElementById('results-btn');
        if (resultsBtn) resultsBtn.style.display = 'block';
        setTimeout(() => {
            window.location.href = `/search?q=${encodeURIComponent(data.query)}`;
        }, 3000);
    }
}

function checkStatus() {
    fetch(`/get_task_status?task_id=${taskId}`)
        .then(response => response.json())
        .then(data => {
            updateTaskStatus(data);
            
            if (data.status !== 'completed') {
                setTimeout(checkStatus, 1000);
            }
        })
        .catch(error => {
            console.error('Error al verificar el estado:', error);
            setTimeout(checkStatus, 3000);
        });
}

        document.addEventListener('DOMContentLoaded', () => {
            if (!taskId) {
                const statusMessage = document.getElementById('status-message');
            if (statusMessage) statusMessage.textContent = 'Error: ID de tarea no especificado';
            return;
        }

            checkStatus();
});
