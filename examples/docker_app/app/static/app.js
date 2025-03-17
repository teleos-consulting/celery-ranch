document.addEventListener('DOMContentLoaded', function() {
    // Create job buttons
    document.querySelectorAll('.create-job-btn').forEach(button => {
        button.addEventListener('click', function() {
            const clientId = this.getAttribute('data-client-id');
            const clientName = this.getAttribute('data-client-name');
            
            document.getElementById('client-id-input').value = clientId;
            document.getElementById('client-name-placeholder').textContent = clientName;
            
            const modal = new bootstrap.Modal(document.getElementById('createJobModal'));
            modal.show();
        });
    });
    
    // Submit job button
    document.getElementById('submit-job').addEventListener('click', function() {
        const clientId = document.getElementById('client-id-input').value;
        const dataSize = document.getElementById('data-size').value;
        
        fetch('/api/jobs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                client_id: parseInt(clientId),
                data_size: parseFloat(dataSize)
            }),
        })
        .then(response => response.json())
        .then(data => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('createJobModal'));
            modal.hide();
            refreshJobs();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to create job');
        });
    });
    
    // Generate jobs form
    document.getElementById('generate-jobs-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const numJobs = document.getElementById('num-jobs').value;
        
        fetch('/api/generate-jobs', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                num_jobs: parseInt(numJobs)
            }),
        })
        .then(response => response.json())
        .then(data => {
            refreshJobs();
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Failed to generate jobs');
        });
    });
    
    // Refresh jobs button
    document.getElementById('refresh-jobs').addEventListener('click', refreshJobs);
    
    // Function to refresh jobs list
    function refreshJobs() {
        fetch('/api/jobs')
        .then(response => response.json())
        .then(jobs => {
            const tableBody = document.getElementById('jobs-table-body');
            tableBody.innerHTML = '';
            
            jobs.slice(0, 10).forEach(job => {
                const row = document.createElement('tr');
                
                const idCell = document.createElement('td');
                idCell.textContent = job.id;
                row.appendChild(idCell);
                
                const clientCell = document.createElement('td');
                clientCell.textContent = `Client ${job.client_id}`;
                row.appendChild(clientCell);
                
                const sizeCell = document.createElement('td');
                sizeCell.textContent = job.data_size.toFixed(2);
                row.appendChild(sizeCell);
                
                const statusCell = document.createElement('td');
                statusCell.textContent = job.status;
                statusCell.className = `job-status-${job.status}`;
                row.appendChild(statusCell);
                
                tableBody.appendChild(row);
            });
        })
        .catch(error => {
            console.error('Error:', error);
        });
    }
    
    // Auto refresh jobs every 5 seconds
    setInterval(refreshJobs, 5000);
});