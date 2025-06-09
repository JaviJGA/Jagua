let taskId = new URLSearchParams(window.location.search).get('task_id');
const progressBar = document.getElementById('progressBar');
const statusMessage = document.getElementById('statusMessage');
const details = document.getElementById('details');
let checkInterval;

//deberiamos de haber dado más javascript en el grado, al menos no es php eh... / Joder no lo sabes bien hermano
function updateProgressBar(progress) {
    const fill = document.getElementById('progress-fill');
    const text = document.getElementById('progress-text');
    fill.style.width = progress + '%';
    text.textContent = progress + '% completado';
}

function updateTaskStatus(data) {
    updateProgressBar(data.progress);
    document.getElementById('status-message').textContent = data.message || '';
    document.getElementById('urls-found').textContent = data.urls_found || '0';
    document.getElementById('urls-indexed').textContent = data.urls_indexed || '0';

    const currentUrl = document.getElementById('current-url');
    if (data.current_url) {
        currentUrl.textContent = data.current_url;
        currentUrl.style.display = 'block';
    } else {
        currentUrl.style.display = 'none';
    }
    
    const loader = document.getElementById('loader');
    loader.style.display = data.status !== 'completed' ? 'block' : 'none';

    if (data.status === 'completed') {
        clearInterval(checkInterval);
        document.getElementById('results-btn').style.display = 'block';
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
        document.getElementById('status-message').textContent = 'Error: ID de tarea no especificado';
        return;
    }


    checkStatus();
});        

//nos e formatear 
function checkProgress() {
    fetch(`/get_task_status?task_id=${taskId}`)
    .then(response => response.json())
    .then(data => {
    progressBar.style.width = data.progress + '%';
    statusMessage.textContent = data.message;
    let detailText = `Progreso: ${data.progress}%`;
    if(data.related_indexed) {
        detailText += ` | Relacionados: ${data.related_indexed}/${data.total_related}`;
    }
    details.textContent = detailText;
    if(data.status !== 'completed') {
        setTimeout(checkProgress, 2000);
    } 
    else {
        setTimeout(() => {
            window.location.href = `/search?q={{ query }}`;
        }, 3000);
    }});
    }
    checkProgress();