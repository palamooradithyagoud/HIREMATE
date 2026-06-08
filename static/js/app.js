/**
 * SkillRecommender — Premium SaaS Frontend Logic
 * Strictly Vanilla JS (no frameworks)
 */

document.addEventListener('DOMContentLoaded', () => {
    // Selectors
    const skillInput = document.getElementById('skill-input');
    const levelDropdown = document.getElementById('level-dropdown');
    const languageDropdown = document.getElementById('language-dropdown');
    const ctaButton = document.getElementById('cta-button');
    const loadingIndicator = document.getElementById('loading');
    const emptyState = document.getElementById('empty-state');
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    // Steps & Grids
    const resultsNav = document.getElementById('results-nav');
    const playlistStep = document.getElementById('playlist-step');
    const certificateStep = document.getElementById('certificate-step');
    const playlistGrid = document.getElementById('playlist-grid');
    const certificateGrid = document.getElementById('certificate-grid');

    // Tabs
    const tabPlaylists = document.getElementById('tab-playlists');
    const tabCertificates = document.getElementById('tab-certificates');
    const tabRoadmap = document.getElementById('tab-roadmap');
    const tierLabelBadge = document.getElementById('tier-label-badge');

    // Roadmap UI
    const roadmapStep = document.getElementById('roadmap-step');
    const roadmapContent = document.getElementById('roadmap-content');
    
    // AI Recommendations UI
    const aiRecommendations = document.getElementById('ai-recommendations');
    const aiRecommendationsGrid = document.getElementById('ai-recommendations-grid');
    const tierIndicator = document.getElementById('tier-indicator');

    // Session ID (anonymous tracking)
    let sessionId = sessionStorage.getItem('sp_sid');
    if (!sessionId) {
        sessionId = 'sp_' + Math.random().toString(36).substr(2, 12);
        sessionStorage.setItem('sp_sid', sessionId);
    }

    // Local results store
    let currentSkill = '';
    let currentResults = {};

    // Saved playlists management state and actions
    let savedPlaylists = [];
    const generateVideosForPlaylist = (title, skill) => {
        const t = (title + ' ' + (skill || '')).toLowerCase();
        let topics = [];
        if (t.includes('java') && !t.includes('javascript')) {
            topics = [
                "Introduction to Java & Setup",
                "Variables and Data Types in Java",
                "Operators & Conditional Logic",
                "Loops in Java (For, While)",
                "Classes, Objects & Constructors",
                "Method Overloading & Overriding",
                "Inheritance & Polymorphism",
                "Abstraction & Interfaces",
                "Packages & Access Modifiers",
                "Exception Handling in Java"
            ];
        } else if (t.includes('python')) {
            topics = [
                "Python Installation & Basics",
                "Control Flow and Loops",
                "Functions & Argument Scope",
                "Lists, Tuples & Dictionaries",
                "File I/O Operations",
                "Object Oriented Python Basics",
                "Modules and PIP Packages",
                "Exception Handling in Python",
                "Lambda & List Comprehensions",
                "Intro to Pandas & NumPy"
            ];
        } else if (t.includes('c++') || t.includes('cpp')) {
            topics = [
                "C++ Introduction & Setup",
                "Variables, Constants & Operators",
                "Control Statements & Loops",
                "Functions & Memory Addresses",
                "Pointers and References",
                "Array Manipulation",
                "Classes and Object Instantiation",
                "Inheritance & Polymorphism",
                "STL Containers & Iterators",
                "File Streams & Exceptions"
            ];
        } else if (t.includes('c ') || t.startsWith('c ') || t.includes(' c ') || t.endsWith(' c') || t.includes('c datastructure') || t.includes('data structure')) {
            topics = [
                "Introduction to DSA & Big O",
                "Arrays & Dynamic Arrays",
                "Singly and Doubly Linked Lists",
                "Stacks & Queues",
                "Recursion & Binary Search",
                "Trees & Binary Search Trees",
                "Heaps & Priority Queues",
                "Graphs Representation (BFS/DFS)",
                "Hashing & Hash Maps",
                "Sorting Algorithms Complexity"
            ];
        } else {
            // General fallback
            topics = [
                "Introduction & Overview",
                "Environment Setup",
                "Variables & Operations",
                "Conditionals & Control Flow",
                "Functions & Parameters",
                "Working with Collections",
                "Errors & Exception Handling",
                "Debugging Techniques",
                "Mini-Project Implementation",
                "Final Review & Next Steps"
            ];
        }
        
        return topics.map((topicName, idx) => ({
            id: idx + 1,
            title: topicName,
            completed: false
        }));
    };

    const getSavedPlaylists = () => {
        return savedPlaylists;
    };

    const togglePlaylistSave = async (playlist, btnEl) => {
        const index = savedPlaylists.findIndex(p => p.url === playlist.url);
        if (index > -1) {
            // Remove it
            savedPlaylists.splice(index, 1);
            if (btnEl) {
                btnEl.textContent = '💾 Save';
                btnEl.classList.remove('saved');
            }
            showToast('Removed from saved playlists');
            syncSavedPlaylists(savedPlaylists);
            renderSavedPlaylists();
        } else {
            // Add it — fetch real videos from YouTube API
            playlist.savedAt = new Date().toISOString();
            playlist.completed = false;

            if (btnEl) {
                btnEl.textContent = '⏳ Loading...';
                btnEl.disabled = true;
            }

            try {
                const resp = await fetch(`/get-playlist-videos?playlist_url=${encodeURIComponent(playlist.url)}`);
                const data = await resp.json();
                if (data.videos && data.videos.length > 0) {
                    playlist.videos = data.videos;
                    showToast(`Saved! ${data.total} videos loaded from playlist`);
                } else {
                    // Fallback to generated videos
                    playlist.videos = generateVideosForPlaylist(playlist.title, playlist.skill);
                    showToast('Saved! (Using estimated video list)');
                }
            } catch (err) {
                console.error('Failed to fetch playlist videos:', err);
                playlist.videos = generateVideosForPlaylist(playlist.title, playlist.skill);
                showToast('Saved! (Using estimated video list)');
            }

            savedPlaylists.push(playlist);
            if (btnEl) {
                btnEl.textContent = '✅ Saved';
                btnEl.classList.add('saved');
                btnEl.disabled = false;
            }
            syncSavedPlaylists(savedPlaylists);
            renderSavedPlaylists();
            
            // Track save event to DB
            trackClick(playlist.url, playlist.title, 'save');
        }
    };

    const togglePlaylistCompleted = (url, isChecked) => {
        const playlist = savedPlaylists.find(p => p.url === url);
        if (playlist) {
            playlist.completed = isChecked;
            playlist.completedAt = isChecked ? new Date().toISOString() : null;
            if (!playlist.videos) {
                playlist.videos = generateVideosForPlaylist(playlist.title, playlist.skill);
            }
            playlist.videos.forEach(v => {
                v.completed = isChecked;
            });
            syncSavedPlaylists(savedPlaylists);
            renderSavedPlaylists();
            showToast(isChecked ? 'All videos completed!' : 'Marked incomplete');

            // Track complete event to DB if marked as complete
            if (isChecked) {
                trackClick(playlist.url, playlist.title, 'complete');
            }
        }
    };

    const toggleVideoCompleted = (playlistUrl, videoId, isChecked) => {
        const playlist = savedPlaylists.find(p => p.url === playlistUrl);
        if (playlist) {
            if (!playlist.videos) {
                playlist.videos = generateVideosForPlaylist(playlist.title, playlist.skill);
            }
            const video = playlist.videos.find(v => v.id === videoId);
            if (video) {
                video.completed = isChecked;
            }
            
            // Re-calculate playlist completion
            const total = playlist.videos.length;
            const completedCount = playlist.videos.filter(v => v.completed).length;
            const wasCompleted = playlist.completed;
            playlist.completed = (completedCount === total);
            playlist.completedAt = playlist.completed ? new Date().toISOString() : null;

            syncSavedPlaylists(savedPlaylists);
            renderSavedPlaylists();
            
            showToast(`Video marked ${isChecked ? 'completed' : 'incomplete'} (${completedCount}/${total})`);

            // Track complete event to DB if all videos were completed by checking this box
            if (playlist.completed && !wasCompleted) {
                trackClick(playlist.url, playlist.title, 'complete');
            }
        }
    };

    const removePlaylist = (url) => {
        savedPlaylists = savedPlaylists.filter(p => p.url !== url);
        syncSavedPlaylists(savedPlaylists);
        renderSavedPlaylists();
        showToast('Removed playlist');
        
        // Also update any visible buttons on screen
        document.querySelectorAll(`.btn-save-playlist[data-url="${url}"]`).forEach(btn => {
            btn.textContent = '💾 Save';
            btn.classList.remove('saved');
        });
    };

    const syncSavedPlaylists = async (savedList) => {
        try {
            await fetch('/sync-saved-playlists', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlists_list: savedList })
            });
        } catch (e) {
            console.error("Failed to sync saved playlists to DB:", e);
        }
    };

    const renderSavedPlaylists = () => {
        const saved = getSavedPlaylists();
        const savedCountEl = document.getElementById('saved-playlists-count');
        const completedCountEl = document.getElementById('completed-playlists-count');
        const listContainer = document.getElementById('saved-playlists-list');

        if (savedCountEl) savedCountEl.textContent = saved.length;
        
        const completedCount = saved.filter(p => p.completed).length;
        if (completedCountEl) completedCountEl.textContent = completedCount;

        if (!listContainer) return;

        if (saved.length === 0) {
            listContainer.innerHTML = `<p class="empty-state" style="padding:10px 0; font-size:0.9rem; margin:0;">No playlists saved yet. Go to the Learning tab to search and save playlists.</p>`;
            return;
        }

        listContainer.innerHTML = '';
        saved.forEach(p => {
            const card = document.createElement('div');
            card.className = 'saved-playlist-card';
            
            const totalCount = p.videos.length;
            const completedCount = p.videos.filter(v => v.completed).length;
            const progressPct = Math.round((completedCount / totalCount) * 100);

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
                    <div class="saved-playlist-info">
                        <div class="saved-playlist-title">${escapeHTML(p.title)}</div>
                        <div class="saved-playlist-meta">
                            ${escapeHTML(p.channel)} | ${escapeHTML(p.skill)} | ${escapeHTML(p.level)}
                        </div>
                    </div>
                    <div class="saved-playlist-actions" style="margin-left: auto;">
                        <label class="saved-playlist-check">
                            <input type="checkbox" class="playlist-complete-checkbox" data-url="${escapeHTML(p.url)}" ${p.completed ? 'checked' : ''}>
                            <span>${p.completed ? '✅ Done' : 'Mark Done'}</span>
                        </label>
                        <a href="${p.url}" target="_blank" class="btn-watch" style="padding: 6px 12px; font-size: 0.75rem; border-radius: var(--radius-sm);">Watch</a>
                        <button class="btn-remove-saved" data-url="${escapeHTML(p.url)}">Delete</button>
                    </div>
                </div>
                
                <!-- Progress Bar -->
                <div style="margin-top: 12px;">
                    <div style="width: 100%; height: 6px; background: var(--border); border-radius: 99px; overflow: hidden; margin-bottom: 4px;">
                        <div style="width: ${progressPct}%; height: 100%; background: var(--success); transition: width 0.3s var(--smooth);"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size: 0.75rem; color: var(--text-sub); font-weight: 500;">
                            ${completedCount} of ${totalCount} videos completed (${progressPct}%)
                        </span>
                        <button class="saved-playlist-videos-toggle" data-expanded="false" style="font-size:0.75rem; color:var(--primary); background:none; border:none; cursor:pointer; font-weight:700;">
                            ▼ Show Videos (${totalCount})
                        </button>
                    </div>
                </div>

                <!-- Collapsible Video Checklist -->
                <div class="playlist-videos-list" style="display: none;">
                    ${p.videos.map(v => `
                        <label class="playlist-video-item ${v.completed ? 'completed' : ''}">
                            <input type="checkbox" class="video-checkbox" data-video-id="${v.id}" ${v.completed ? 'checked' : ''}>
                            <span>${v.id}. ${escapeHTML(v.title)}</span>
                            ${v.videoId ? `<a href="https://www.youtube.com/watch?v=${v.videoId}" target="_blank" class="video-play-link" title="Watch on YouTube">▶</a>` : ''}
                        </label>
                    `).join('')}
                </div>
            `;

            // Expand/Collapse Listener
            const toggleBtn = card.querySelector('.saved-playlist-videos-toggle');
            const videosList = card.querySelector('.playlist-videos-list');
            toggleBtn.addEventListener('click', () => {
                const isExpanded = toggleBtn.getAttribute('data-expanded') === 'true';
                if (isExpanded) {
                    videosList.style.display = 'none';
                    toggleBtn.setAttribute('data-expanded', 'false');
                    toggleBtn.textContent = `▼ Show Videos (${totalCount})`;
                } else {
                    videosList.style.display = 'flex';
                    toggleBtn.setAttribute('data-expanded', 'true');
                    toggleBtn.textContent = `▲ Hide Videos`;
                }
            });

            // General Playlist Completion Checkbox Listener
            card.querySelector('.playlist-complete-checkbox').addEventListener('change', (e) => {
                togglePlaylistCompleted(p.url, e.target.checked);
            });

            // Individual Video Checkboxes Listeners
            card.querySelectorAll('.video-checkbox').forEach(cb => {
                cb.addEventListener('change', (e) => {
                    const videoId = parseInt(e.target.getAttribute('data-video-id'));
                    toggleVideoCompleted(p.url, videoId, e.target.checked);
                });
            });

            card.querySelector('.btn-remove-saved').addEventListener('click', () => {
                removePlaylist(p.url);
            });

            listContainer.appendChild(card);
        });
    };

    const initSavedPlaylists = async () => {
        try {
            const res = await fetch('/get-saved-playlists');
            if (res.ok) {
                const list = await res.json();
                if (Array.isArray(list)) {
                    let changed = false;
                    savedPlaylists = list.map(p => {
                        if (!p.videos || p.videos.length === 0) {
                            p.videos = generateVideosForPlaylist(p.title, p.skill);
                            changed = true;
                        }
                        return p;
                    });
                    if (changed) {
                        syncSavedPlaylists(savedPlaylists);
                    }
                }
            }
        } catch (e) {
            console.error("Failed to fetch saved playlists from DB:", e);
        }
        renderSavedPlaylists();
    };

    // Silent click tracker
    const trackClick = (url, title, action = 'click') => {
        if (!url || url === '#') return;
        fetch('/track-click', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                resource_url: url,
                resource_title: title,
                skill_name: currentSkill,
                action,
                session_id: sessionId
            })
        }).catch(() => {});
    };

    /**
     * Handle Search
     */
    const handleSearch = async () => {
        const skill = skillInput.value.trim();
        const level = levelDropdown.value;
        const language = languageDropdown.value;

        if (!skill) {
            showToast('Please enter a skill to learn.');
            return;
        }

        // Reset UI
        setLoading(true);
        resetViews();
        emptyState.innerHTML = `<p>Enter a skill above to generate your learning path.</p>`;

        try {
            const response = await fetch('/get-resource', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ skill, level, language })
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to fetch resources.');
            }

            const data = await response.json();
            currentResults = data;

            currentSkill = skill;

            const hasPlaylists = data.fallback_playlists && data.fallback_playlists.length > 0;
            const hasCerts = data.fallback_certs && data.fallback_certs.length > 0;
            const hasRecommendations = data.recommendations;

            if (!hasPlaylists && !hasCerts && !hasRecommendations) {
                setLoading(false);
                emptyState.style.display = 'block';
                return;
            }

            // Tier label badge
            if (tierLabelBadge) tierLabelBadge.textContent = data.tier_label || '';

            if (data.tier === 0) {
                tierIndicator.textContent = '⚡ Instant Result: Retrieved from AI Memory';
            } else if (data.tier === 1) {
                tierIndicator.textContent = '🚀 Curated Result: Trusted CSV Dataset';
            } else if (data.tier >= 3) {
                tierIndicator.textContent = '🧠 AI-Ranked Result: Groq Intelligence Engine';
            } else {
                tierIndicator.textContent = 'The best free curated playlists to build your foundation.';
            }

            if (data.roadmap) {
                tabRoadmap.style.display = 'inline-block';
            } else {
                tabRoadmap.style.display = 'none';
            }

            // Show Navigation and Step 1
            resultsNav.style.display = 'flex';
            renderStep('playlists');

            // Save to Supabase (fire and forget)
            if (window.db && window.db.saveSearch) {
                window.db.saveSearch(skill, level, language);
            }

        } catch (error) {
            if (error.message.includes("No verified high-quality")) {
                emptyState.innerHTML = `<p style="color: var(--danger); font-size: 1.1rem; font-weight: 500;">❌ ${escapeHTML(error.message)}</p>`;
            } else {
                showToast(error.message);
            }
            emptyState.style.display = 'block';
        } finally {
            setLoading(false);
        }
    };

    const renderAIMentorCard = (category, data) => {
        const card = document.createElement('div');
        card.className = 'resource-card show';
        const vStatus = data.verification_status ? `<span class="pill-badge" style="background: #059669; color: white; margin-left: auto;">${escapeHTML(data.verification_status)}</span>` : '';
        
        const savedList = getSavedPlaylists();
        const isSaved = savedList.some(p => p.url === data.url);
        const saveBtnLabel = isSaved ? '✅ Saved' : '💾 Save';
        const saveBtnClass = isSaved ? 'btn-save-playlist saved' : 'btn-save-playlist';

        card.innerHTML = `
            <div class="card-header" style="flex-wrap: wrap;">
                <span class="pill-badge" style="background: var(--primary); color: white;">${escapeHTML(category.toUpperCase())}</span>
                <span class="pill-badge">Trust: ${data.trust_score || 90}/100</span>
                ${vStatus}
            </div>
            <h3 class="card-title">${escapeHTML(data.title)}</h3>
            <span class="channel-name">${escapeHTML(data.channel)}</span>
            <p class="card-desc" style="margin-top: 10px;"><strong>💡 Why:</strong> ${escapeHTML(data.why_selected)}</p>
            <p class="card-desc"><strong>⏱️ Time:</strong> ${escapeHTML(data.estimated_time)} | <strong>🎯 Outcome:</strong> ${escapeHTML(data.expected_outcome)}</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: auto;">
                <a href="${data.url}" target="_blank" class="btn-watch" rel="noopener noreferrer"
                   style="background: var(--primary); border-color: transparent;"
                   onclick="trackClickGlobal('${data.url.replace(/'/g,"\\'")}',' ${escapeHTML(data.title).replace(/'/g,"\\'")}')">Watch Playlist</a>
                <button class="${saveBtnClass}" data-url="${escapeHTML(data.url)}">
                    ${saveBtnLabel}
                </button>
            </div>
        `;

        const saveBtn = card.querySelector('.btn-save-playlist');
        saveBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            togglePlaylistSave({
                title: data.title,
                channel: data.channel,
                url: data.url,
                duration: data.estimated_time || 'Full',
                level: 'All',
                skill: category
            }, saveBtn);
        });

        return card;
    };

    /**
     * Render a specific view step
     */
    const renderStep = (step) => {
        // Reset all
        playlistStep.classList.remove('active');
        certificateStep.classList.remove('active');
        roadmapStep.classList.remove('active');
        tabPlaylists.classList.remove('active');
        tabCertificates.classList.remove('active');
        tabRoadmap.classList.remove('active');

        if (step === 'playlists') {
            playlistGrid.innerHTML = '';
            aiRecommendationsGrid.innerHTML = '';
            playlistStep.classList.add('active');
            tabPlaylists.classList.add('active');
            
            if (currentResults.recommendations) {
                aiRecommendations.style.display = 'block';
                Object.entries(currentResults.recommendations).forEach(([category, data], index) => {
                    if(data && data.url) {
                        const card = renderAIMentorCard(category.replace('_', ' '), data);
                        aiRecommendationsGrid.appendChild(card);
                    }
                });
            } else {
                aiRecommendations.style.display = 'none';
            }

            if (currentResults.fallback_playlists) {
                currentResults.fallback_playlists.forEach((item, index) => {
                    const card = createCard(item, index);
                    playlistGrid.appendChild(card);
                    setTimeout(() => card.classList.add('show'), (index + 2) * 100);
                });
            }
        } 
        else if (step === 'certificates') {
            certificateGrid.innerHTML = '';
            certificateStep.classList.add('active');
            tabCertificates.classList.add('active');

            if (currentResults.fallback_certs) {
                currentResults.fallback_certs.forEach((item, index) => {
                    const card = createCard(item, index);
                    certificateGrid.appendChild(card);
                    setTimeout(() => card.classList.add('show'), index * 100);
                });
            }
        }
        else if (step === 'roadmap') {
            roadmapContent.innerHTML = '';
            roadmapStep.classList.add('active');
            tabRoadmap.classList.add('active');

            const rm = currentResults.roadmap;
            if (rm) {
                roadmapContent.innerHTML = `
                    <div class="roadmap-section">
                        <h3 style="font-family:'Outfit',sans-serif; margin-bottom:8px;">🌱 Beginner Phase</h3>
                        <ul class="detailed-list">${(rm.beginner || []).map(i => `<li>${escapeHTML(i)}</li>`).join('')}</ul>
                    </div>
                    <div class="roadmap-section">
                        <h3 style="font-family:'Outfit',sans-serif; margin-bottom:8px;">🔥 Intermediate Phase</h3>
                        <ul class="detailed-list">${(rm.intermediate || []).map(i => `<li>${escapeHTML(i)}</li>`).join('')}</ul>
                    </div>
                    <div class="roadmap-section">
                        <h3 style="font-family:'Outfit',sans-serif; margin-bottom:8px;">🚀 Advanced Phase</h3>
                        <ul class="detailed-list">${(rm.advanced || []).map(i => `<li>${escapeHTML(i)}</li>`).join('')}</ul>
                    </div>
                    <div class="roadmap-section">
                        <h3 style="font-family:'Outfit',sans-serif; margin-bottom:8px;">🛠️ Projects to Build</h3>
                        <div class="projects-mini-list" style="display:flex; flex-direction:column; gap:10px;">
                            ${(rm.projects || []).map(p => `<div class="action-box"><strong>${escapeHTML(p.name || p.title || 'Project')}:</strong> ${escapeHTML(p.description || '')}</div>`).join('')}
                        </div>
                    </div>
                    <div class="roadmap-section">
                        <h3 style="font-family:'Outfit',sans-serif; margin-bottom:8px;">🏆 Recommended Certifications</h3>
                        <ul class="keyword-tags" style="display:flex; flex-wrap:wrap; gap:8px; list-style:none;">${(rm.certifications || []).map(c => `<li><span class="pill-badge" style="background:var(--primary-light); color:var(--primary); border-color:transparent;">${escapeHTML(c)}</span></li>`).join('')}</ul>
                    </div>
                    <div class="roadmap-section">
                        <h3 style="font-family:'Outfit',sans-serif; margin-bottom:8px;">💼 Interview Prep Focus</h3>
                        <ul class="detailed-list">${(rm.interview_prep || []).map(i => `<li>${escapeHTML(i)}</li>`).join('')}</ul>
                    </div>
                `;
            }
        }
    };

    /**
     * Card Factory
     */
    const createCard = (data, index) => {
        const card = document.createElement('div');
        card.className = 'resource-card';
        
        const title = data.title || 'Untitled';
        const channel = data.channel || 'Author';
        const duration = data.duration_hours ? `${data.duration_hours}h` : 'Full';
        const level = data.level || 'Beginner';
        const desc = data.description || 'Curated high-quality learning resource.';
        const url = data.url || '#';
        const rank = data.rank || (index + 1);

        const isCert = !url.includes('youtube.com');
        const btnLabel = isCert ? 'Join Course' : 'Watch Playlist';

        const vBadge = data.verification_status ? `<span class="pill-badge" style="background: #059669; color: white;">${escapeHTML(data.verification_status)}</span>` : '';
        
        const savedList = getSavedPlaylists();
        const isSaved = savedList.some(p => p.url === url);
        const saveBtnLabel = isSaved ? '✅ Saved' : '💾 Save';
        const saveBtnClass = isSaved ? 'btn-save-playlist saved' : 'btn-save-playlist';

        card.innerHTML = `
            <div class="card-header" style="flex-wrap: wrap;">
                <span class="rank-badge">#${rank}</span>
                <div class="card-badges" style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <span class="pill-badge">${escapeHTML(level)}</span>
                    <span class="pill-badge">${escapeHTML(duration)}</span>
                    ${vBadge}
                </div>
            </div>
            <h3 class="card-title">${escapeHTML(title)}</h3>
            <span class="channel-name">${escapeHTML(channel)}</span>
            <p class="card-desc">${escapeHTML(desc)}</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: auto;">
                <a href="${url}" target="_blank" class="btn-watch" rel="noopener noreferrer">
                    ${btnLabel}
                </a>
                <button class="${saveBtnClass}" data-url="${escapeHTML(url)}">
                    ${saveBtnLabel}
                </button>
            </div>
        `;
        
        const saveBtn = card.querySelector('.btn-save-playlist');
        saveBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            togglePlaylistSave({
                title,
                channel,
                url,
                duration,
                level,
                skill: currentSkill || level
            }, saveBtn);
        });

        return card;
    };

    // UI Helpers
    const resetViews = () => {
        resultsNav.style.display = 'none';
        playlistStep.classList.remove('active');
        certificateStep.classList.remove('active');
        roadmapStep.classList.remove('active');
        emptyState.style.display = 'none';
        playlistGrid.innerHTML = '';
        certificateGrid.innerHTML = '';
        aiRecommendationsGrid.innerHTML = '';
        roadmapContent.innerHTML = '';
    };

    const setLoading = (isLoading) => {
        loadingIndicator.style.display = isLoading ? 'block' : 'none';
        ctaButton.disabled = isLoading;
        ctaButton.textContent = isLoading ? 'Curating...' : 'Find Resources';
    };

    const showToast = (message) => {
        toastMessage.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 4000);
    };

    const escapeHTML = (str) => {
        const p = document.createElement('p');
        p.textContent = str;
        return p.innerHTML;
    };

    /**
     * Interview Prep Logic
     */
    const interviewCategories = document.getElementById('interview-categories');
    
    // DSA Sub-View
    const dsaPrepContent = document.getElementById('dsa-prep-content');
    const btnDsaCategory = document.getElementById('btn-dsa-category');
    const backToCategoriesDsa = document.getElementById('back-to-categories-dsa');
    const companySearchInput = document.getElementById('company-search');
    const companiesGrid = document.getElementById('companies-grid');
    const questionsView = document.getElementById('questions-view');
    const companySelection = document.getElementById('company-selection');
    const backToCompanies = document.getElementById('back-to-companies');
    const questionsGrid = document.getElementById('questions-grid');
    const selectedCompanyTitle = document.getElementById('selected-company-title');

    // Resume Sub-View
    const resumeAnalyzerContent = document.getElementById('resume-analyzer-content');
    const btnResumeCategory = document.getElementById('btn-resume-category');
    const backToCategoriesResume = document.getElementById('back-to-categories-resume');
    const resumeUpload = document.getElementById('resume-upload');
    const btnTriggerUpload = document.getElementById('btn-trigger-upload');
    const uploadZone = document.getElementById('upload-zone');
    const analysisStatus = document.getElementById('analysis-status');
    const analysisResults = document.getElementById('analysis-results');
    const statusText = document.getElementById('status-text');

    let allCompanies = [];

    const showSelectionScreen = () => {
        if (interviewCategories) interviewCategories.style.display = 'grid';
        if (dsaPrepContent) dsaPrepContent.style.display = 'none';
        if (resumeAnalyzerContent) resumeAnalyzerContent.style.display = 'none';
    };

    const enterDsaPrep = async () => {
        if (interviewCategories) interviewCategories.style.display = 'none';
        if (dsaPrepContent) dsaPrepContent.style.display = 'block';
        if (companySelection) companySelection.style.display = 'block';
        if (questionsView) questionsView.style.display = 'none';
        
        if (allCompanies.length === 0) {
            await fetchCompanies();
        }
        renderCompanies(allCompanies);
    };

    const enterResumeAnalyzer = () => {
        if (interviewCategories) interviewCategories.style.display = 'none';
        if (resumeAnalyzerContent) resumeAnalyzerContent.style.display = 'block';
        if (uploadZone) uploadZone.style.display = 'block';
        if (analysisStatus) analysisStatus.style.display = 'none';
        if (analysisResults) analysisResults.style.display = 'none';
    };

    const fetchCompanies = async () => {
        try {
            const res = await fetch('/get-companies');
            allCompanies = await res.json();
        } catch (err) {
            showToast('Failed to load companies.');
        }
    };

    const renderCompanies = (list) => {
        companiesGrid.innerHTML = '';
        list.forEach(name => {
            const badge = document.createElement('div');
            badge.className = 'company-badge';
            badge.textContent = name;
            badge.onclick = () => loadCompanyQuestions(name);
            companiesGrid.appendChild(badge);
        });
    };

    // ---- Smart Filtering Variables ----
    let currentQuestions = [];
    const filterDifficulty = document.getElementById('filter-difficulty');
    const filterStatus = document.getElementById('filter-status');
    const companySearch = document.getElementById('company-search');

    const inferTopic = (title, url) => {
        const t = (title + ' ' + (url||'')).toLowerCase();
        if (t.includes('tree')) return 'Trees';
        if (t.includes('graph')) return 'Graphs';
        if (t.includes('array') || t.includes('matrix')) return 'Arrays';
        if (t.includes('string')) return 'Strings';
        if (t.includes('list') || t.includes('node')) return 'Linked Lists';
        if (t.includes('dp') || t.includes('dynamic') || t.includes('profit')) return 'Dynamic Prog.';
        return 'Misc';
    };

    const DIFFICULTY_CLASS = { Easy: 'diff-easy', Medium: 'diff-medium', Hard: 'diff-hard' };

    const renderQuestions = (questions) => {
        questionsGrid.innerHTML = '';
        if (!questions || questions.length === 0) {
            questionsGrid.innerHTML = '<p class="empty-state">No questions found.</p>';
            return;
        }

        const solvedList = getSolvedQuestions();
        const diffFilter = filterDifficulty ? filterDifficulty.value : 'All';
        const statFilter = filterStatus ? filterStatus.value : 'All';

        let filtered = questions.filter(q => {
            const isSolved = solvedList.some(s => s.link === q.url);
            if (diffFilter !== 'All' && q.difficulty !== diffFilter) return false;
            if (statFilter === 'Completed' && !isSolved) return false;
            if (statFilter === 'Pending' && isSolved) return false;
            return true;
        });

        if (filtered.length === 0) {
            questionsGrid.innerHTML = '<p class="empty-state">No questions match your filters.</p>';
            return;
        }

        filtered.forEach((q, index) => {
            const card = document.createElement('div');
            card.className = 'resource-card show';
            
            const id         = q.id         || '';
            const name       = q.title       || 'Unknown Problem';
            const link       = q.url         || '#';
            const difficulty = q.difficulty  || '';
            const topic      = inferTopic(name, link);
            const acceptance = q.acceptance  || '';
            const frequency  = q.frequency   || '';
            const others     = q.other_companies || [];
            const isSolved   = solvedList.some(s => s.link === link);

            const diffClass  = DIFFICULTY_CLASS[difficulty] || '';
            const freqNum    = parseFloat(frequency) || 0;

            card.innerHTML = `
                <div class="card-header">
                    ${id ? `<span class="rank-badge lc-id">#${escapeHTML(id)}</span>` : `<span class="rank-badge">#${index + 1}</span>`}
                    <div class="card-badges">
                        ${difficulty ? `<span class="pill-badge diff-pill ${diffClass}">${escapeHTML(difficulty)}</span>` : ''}
                        <span class="pill-badge" style="background:rgba(0,0,0,0.03); border-color:transparent;">${topic}</span>
                    </div>
                </div>

                <div class="card-check-wrap">
                    <input type="checkbox" class="solve-checkbox"
                        data-link="${link}"
                        data-name="${escapeHTML(name)}"
                        data-diff="${difficulty}"
                        data-topic="${topic}"
                        ${isSolved ? 'checked' : ''}>
                    <span class="solve-label">${isSolved ? '✅ Solved' : 'Mark as Solved'}</span>
                </div>

                <h3 class="card-title">${escapeHTML(name)}</h3>

                <div style="font-size:0.75rem; color:var(--text-sub); display:flex; gap:12px; margin-bottom:8px;">
                    ${acceptance ? `<span>Acceptance: <strong>${escapeHTML(acceptance)}</strong></span>` : ''}
                    ${frequency  ? `<span>Frequency: <strong>${escapeHTML(frequency)}</strong></span>` : ''}
                </div>

                ${freqNum > 0 ? `
                <div style="height:4px; background:#e2e8f0; border-radius:99px; overflow:hidden; margin-bottom:12px; width:100%;">
                    <div style="height:100%; background:var(--primary); width:${Math.min(freqNum, 100)}%;"></div>
                </div>` : ''}

                ${others.length > 0 ? `
                <div class="other-companies-wrap">
                    <span style="font-size:0.65rem; color:var(--text-muted); width:100%;">Also asked at:</span>
                    ${others.slice(0, 5).map(c => `<span class="other-comp-tag">${escapeHTML(c)}</span>`).join('')}
                    ${others.length > 5 ? `<span class="other-comp-tag">+${others.length - 5} more</span>` : ''}
                </div>` : ''}

                <a href="${link}" target="_blank" class="btn-watch" rel="noopener noreferrer" style="margin-top:16px;">
                    Solve on LeetCode →
                </a>
            `;

            const checkbox = card.querySelector('.solve-checkbox');
            checkbox.addEventListener('change', (e) => {
                toggleSolved({ link, name, difficulty, topic }, e.target.checked);
                card.querySelector('.solve-label').textContent = e.target.checked ? '✅ Solved' : 'Mark as Solved';
                updateCommandCenter();
            });

            questionsGrid.appendChild(card);
        });
    };

    if (filterDifficulty) filterDifficulty.addEventListener('change', () => renderQuestions(currentQuestions));
    if (filterStatus) filterStatus.addEventListener('change', () => renderQuestions(currentQuestions));

    const loadCompanyQuestions = async (company) => {
        companySelection.style.display = 'none';
        questionsView.style.display = 'block';
        selectedCompanyTitle.textContent = company;
        questionsGrid.innerHTML = '<div class="loading-indicator" style="display:block;"><div class="spinner"></div><p>Fetching questions...</p></div>';

        try {
            const res = await fetch(`/get-questions?company=${encodeURIComponent(company)}`);
            const data = await res.json();
            currentQuestions = data.questions;
            renderQuestions(currentQuestions);
        } catch (err) {
            showToast('Failed to load questions.');
        }
    };

    /**
     * Solved Questions State & Command Center Automation
     */
    let solvedDsaQuestions = [];
    
    const getSolvedQuestions = () => {
        return solvedDsaQuestions;
    };

    const toggleSolved = (q, isChecked) => {
        if (isChecked) {
            if (!solvedDsaQuestions.find(s => s.link === q.link)) {
                solvedDsaQuestions.push({ ...q, solvedAt: new Date().toISOString(), revisions: 0 });
            } else {
                let existing = solvedDsaQuestions.find(s => s.link === q.link);
                existing.revisions = (existing.revisions || 0) + 1;
            }
        } else {
            solvedDsaQuestions = solvedDsaQuestions.filter(s => s.link !== q.link);
        }

        // Sync to backend Supabase database
        fetch('/sync-dsa-progress', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ solved_list: solvedDsaQuestions })
        }).catch(err => console.error("DSA sync failed:", err));
    };

    let charts = {};
    const updateCommandCenter = () => {
        const solved = getSolvedQuestions();
        const GOAL = 500;
        
        // 1. Calculate stats
        const totalSolved = solved.length;
        const completionPct = Math.min(100, Math.round((totalSolved / GOAL) * 100));
        const totalRevisions = solved.reduce((acc, s) => acc + (s.revisions || 0), 0);
        
        // Calculate Streak
        let streak = 0;
        let dates = [...new Set(solved.map(s => new Date(s.solvedAt).toDateString()))].sort((a,b)=>new Date(b)-new Date(a));
        if (dates.length > 0) {
            let curr = new Date();
            for(let d of dates) {
                if (new Date(d).toDateString() === curr.toDateString() || streak === 0 && (curr - new Date(d)) < 172800000) {
                    streak++;
                    curr.setDate(curr.getDate() - 1);
                } else break;
            }
        }

        // Calculate Topic & Difficulty Counts
        const counts = { Easy: 0, Medium: 0, Hard: 0 };
        const topicCounts = {};
        solved.forEach(s => {
            counts[s.difficulty || 'Easy']++;
            topicCounts[s.topic || 'Misc'] = (topicCounts[s.topic || 'Misc'] || 0) + 1;
        });

        const readinessRaw = (counts.Hard * 3 + counts.Medium * 2 + counts.Easy * 1);
        const readinessScore = Math.min(100, Math.round((readinessRaw / (GOAL * 2)) * 100));
        let rank = readinessScore < 30 ? 'Novice' : readinessScore < 70 ? 'Proficient' : 'Elite';

        // 2. Update Sidebar Streak Widget
        document.getElementById('sidebar-streak-days').textContent = `${streak} days`;

        // 3. Update Dashboard Progress Card
        const progressPctText = document.getElementById('dashboard-progress-pct');
        const progressCountText = document.getElementById('dashboard-progress-count');
        const progressRingBar = document.getElementById('dashboard-progress-ring-bar');

        // Calculate real playlist progress
        const savedPl = getSavedPlaylists();
        let totalPlaylistVideos = 0;
        let completedPlaylistVideos = 0;
        savedPl.forEach(p => {
            if (p.videos) {
                totalPlaylistVideos += p.videos.length;
                completedPlaylistVideos += p.videos.filter(v => v.completed).length;
            }
        });

        // Overall progress = combination of DSA + playlist progress
        const dsaPct = Math.min(100, Math.round((totalSolved / GOAL) * 100));
        const overallTopics = totalSolved + completedPlaylistVideos;
        const overallTotal = GOAL + totalPlaylistVideos;
        const overallPct = overallTotal > 0 ? Math.min(100, Math.round((overallTopics / overallTotal) * 100)) : 0;

        progressPctText.textContent = `${overallPct}%`;
        progressCountText.textContent = `${overallTopics} / ${overallTotal} topics`;
        
        // SVG Ring calculations (circumference = 314.16)
        const offset = 314.16 - (314.16 * overallPct / 100);
        progressRingBar.style.strokeDashoffset = offset;

        // Progress Bars Fill — DSA uses real data
        document.getElementById('dsa-progress-label-pct').textContent = `${dsaPct}%`;
        document.getElementById('dsa-progress-bar-fill').style.width = `${dsaPct}%`;
        
        // System Design — based on saved playlists with "system design" in title
        const sdPlaylists = savedPl.filter(p => (p.title + ' ' + (p.skill || '')).toLowerCase().includes('system'));
        const sdTotal = sdPlaylists.reduce((a, p) => a + (p.videos ? p.videos.length : 0), 0);
        const sdDone = sdPlaylists.reduce((a, p) => a + (p.videos ? p.videos.filter(v => v.completed).length : 0), 0);
        const sdPct = sdTotal > 0 ? Math.round((sdDone / sdTotal) * 100) : 0;
        document.getElementById('sd-progress-label-pct').textContent = `${sdPct}%`;
        document.getElementById('sd-progress-bar-fill').style.width = `${sdPct}%`;
        
        // AI/ML — based on saved playlists with "ai" or "ml" or "machine" in title
        const aiPlaylists = savedPl.filter(p => /(ai|ml|machine|deep|neural)/i.test(p.title + ' ' + (p.skill || '')));
        const aiTotal = aiPlaylists.reduce((a, p) => a + (p.videos ? p.videos.length : 0), 0);
        const aiDone = aiPlaylists.reduce((a, p) => a + (p.videos ? p.videos.filter(v => v.completed).length : 0), 0);
        const aiPct = aiTotal > 0 ? Math.round((aiDone / aiTotal) * 100) : 0;
        document.getElementById('aiml-progress-label-pct').textContent = `${aiPct}%`;
        document.getElementById('aiml-progress-bar-fill').style.width = `${aiPct}%`;
        
        // Dev — remaining playlists (not SD/AI categorized)
        const devPlaylists = savedPl.filter(p => !sdPlaylists.includes(p) && !aiPlaylists.includes(p));
        const devTotal = devPlaylists.reduce((a, p) => a + (p.videos ? p.videos.length : 0), 0);
        const devDone = devPlaylists.reduce((a, p) => a + (p.videos ? p.videos.filter(v => v.completed).length : 0), 0);
        const devPct = devTotal > 0 ? Math.round((devDone / devTotal) * 100) : 0;
        document.getElementById('dev-progress-label-pct').textContent = `${devPct}%`;
        document.getElementById('dev-progress-bar-fill').style.width = `${devPct}%`;

        // 4. Update Resume Score Card
        loadResumeScore();

        // 5. Update Practice Overview KPIs — real data
        document.getElementById('overview-solved-count').textContent = totalSolved;
        document.getElementById('overview-success-rate').textContent = totalSolved > 0 ? `${Math.round((counts.Easy * 100 + counts.Medium * 70 + counts.Hard * 50) / Math.max(1, totalSolved))}%` : '0%';
        document.getElementById('overview-streak').textContent = streak;

        // 6. Draw Dashboard Consistency Chart
        drawDashboardConsistencyChart(solved);

        // 7. Draw Dashboard Skill Distribution (doughnut)
        drawDashboardSkillDistribution();

        // 8. Draw Sidebar Streak Sparkline
        drawSidebarStreakSparkline();
    };

    let latestResumeAnalysis = null;

    const loadResumeScore = async () => {
        try {
            const res = await fetch('/get-latest-resume');
            if (res.ok) {
                const dbData = await res.json();
                if (dbData) {
                    latestResumeAnalysis = dbData;
                }
            }
        } catch (e) {
            console.error("Failed to load resume analysis from DB:", e);
        }

        const data = latestResumeAnalysis;
        if (data) {
            document.getElementById('dashboard-resume-score').textContent = `${data.score}/100`;
            const verdictEl = document.getElementById('dashboard-resume-verdict');
            verdictEl.textContent = data.verdict;
            verdictEl.className = 'score-verdict';
            if (data.verdict.toLowerCase().includes('reject') || data.verdict.toLowerCase().includes('no')) {
                verdictEl.classList.add('text-danger');
            } else if (data.verdict.toLowerCase().includes('borderline')) {
                verdictEl.classList.add('text-warning');
            } else {
                verdictEl.classList.add('text-success');
            }
            document.getElementById('dashboard-resume-impact').textContent = data.impact;
            document.getElementById('dashboard-resume-skills').textContent = data.match;
            document.getElementById('dashboard-resume-ats').textContent = typeof data.ats === 'number' ? `${data.ats}%` : data.ats;
        } else {
            // No resume uploaded yet — show empty state
            document.getElementById('dashboard-resume-score').textContent = '—/100';
            const verdictEl = document.getElementById('dashboard-resume-verdict');
            verdictEl.textContent = 'Not analyzed yet';
            verdictEl.className = 'score-verdict';
            document.getElementById('dashboard-resume-impact').textContent = '—';
            document.getElementById('dashboard-resume-skills').textContent = '—';
            document.getElementById('dashboard-resume-ats').textContent = '—';
        }
    };

    // --- CHART BUILDERS (Light Theme configured) ---
    const drawDashboardConsistencyChart = (solved) => {
        if (!window.Chart) return;
        const ctx = document.getElementById('dashboardConsistencyChart');
        if (!ctx) return;

        if (charts.dashCons) charts.dashCons.destroy();

        const last7 = [...Array(7)].map((_, i) => {
            const d = new Date();
            d.setDate(d.getDate() - i);
            return d.toDateString();
        }).reverse();
        
        // Use zeroed trend if no activity yet
        let trendData = [0, 0, 0, 0, 0, 0, 0];
        if (solved && solved.length > 0) {
            const calculated = last7.map(date => solved.filter(s => new Date(s.solvedAt).toDateString() === date).length * 10);
            trendData = calculated;
        }

        charts.dashCons = new Chart(ctx, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Practice Score',
                    data: trendData,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.05)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 4
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, border: { display: false }, ticks: { color: '#94a3b8' } },
                    y: { display: false }
                }
            }
        });
    };

    const drawDashboardSkillDistribution = () => {
        if (!window.Chart) return;
        const ctx = document.getElementById('dashboardSkillDistributionChart');
        if (!ctx) return;

        if (charts.dashDist) charts.dashDist.destroy();

        // Calculate real distribution from solved DSA + saved playlists
        const solved = getSolvedQuestions();
        const savedPl = getSavedPlaylists();
        const dsaCount = solved.length;
        const sdCount = savedPl.filter(p => (p.title + ' ' + (p.skill || '')).toLowerCase().includes('system')).length;
        const aiCount = savedPl.filter(p => /(ai|ml|machine|deep|neural)/i.test(p.title + ' ' + (p.skill || ''))).length;
        const devCount = savedPl.filter(p => {
            const t = (p.title + ' ' + (p.skill || '')).toLowerCase();
            return !t.includes('system') && !/(ai|ml|machine|deep|neural)/i.test(t);
        }).length;

        // If no data at all, show equal placeholder
        const hasData = dsaCount + sdCount + aiCount + devCount > 0;
        const chartData = hasData ? [dsaCount, sdCount, aiCount, devCount] : [1, 1, 1, 1];

        // Update legend percentages in UI
        const dsaPctText = document.getElementById('legend-pct-dsa');
        const sdPctText = document.getElementById('legend-pct-sd');
        const aiPctText = document.getElementById('legend-pct-aiml');
        const devPctText = document.getElementById('legend-pct-dev');

        if (hasData) {
            const totalCount = dsaCount + sdCount + aiCount + devCount;
            if (dsaPctText) dsaPctText.textContent = `${Math.round(dsaCount / totalCount * 100)}%`;
            if (sdPctText) sdPctText.textContent = `${Math.round(sdCount / totalCount * 100)}%`;
            if (aiPctText) aiPctText.textContent = `${Math.round(aiCount / totalCount * 100)}%`;
            if (devPctText) devPctText.textContent = `${Math.round(devCount / totalCount * 100)}%`;
        } else {
            if (dsaPctText) dsaPctText.textContent = `0%`;
            if (sdPctText) sdPctText.textContent = `0%`;
            if (aiPctText) aiPctText.textContent = `0%`;
            if (devPctText) devPctText.textContent = `0%`;
        }

        charts.dashDist = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['DSA', 'System Design', 'AI/ML', 'Development'],
                datasets: [{
                    data: chartData,
                    backgroundColor: hasData
                        ? ['#3b82f6', '#10b981', '#f59e0b', '#6366f1']
                        : ['#e5e7eb', '#e5e7eb', '#e5e7eb', '#e5e7eb'],
                    borderWidth: 4,
                    borderColor: '#ffffff',
                    hoverOffset: 4
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                cutout: '75%'
            }
        });
    };

    const drawSidebarStreakSparkline = () => {
        if (!window.Chart) return;
        const ctx = document.getElementById('sidebarSparklineCanvas');
        if (!ctx) return;

        if (charts.sparkline) charts.sparkline.destroy();

        // Calculate real activity per day for last 7 days
        const solved = getSolvedQuestions();
        const last7 = [];
        for (let i = 6; i >= 0; i--) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            const dayStr = d.toDateString();
            const count = solved.filter(s => new Date(s.solvedAt).toDateString() === dayStr).length;
            last7.push(count);
        }

        charts.sparkline = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [1, 2, 3, 4, 5, 6, 7],
                datasets: [{
                    data: last7,
                    borderColor: '#f97316',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: { display: false }
                }
            }
        });
    };

    const renderAnalyticsCharts = () => {
        if (!window.Chart) return;
        const solved = getSolvedQuestions();
        const counts = { Easy: 0, Medium: 0, Hard: 0 };
        const topicCounts = {};
        solved.forEach(s => {
            counts[s.difficulty || 'Easy']++;
            topicCounts[s.topic || 'Misc'] = (topicCounts[s.topic || 'Misc'] || 0) + 1;
        });

        // Analytics Difficulty Chart
        const diffCtx = document.getElementById('analyticsDifficultyChart');
        if (diffCtx) {
            if (charts.analyticsDiff) charts.analyticsDiff.destroy();
            const hasDsaData = solved.length > 0;
            const diffData = hasDsaData ? [counts.Easy, counts.Medium, counts.Hard] : [1, 1, 1];
            const diffColors = hasDsaData ? ['#10b981', '#f59e0b', '#ef4444'] : ['#e5e7eb', '#e5e7eb', '#e5e7eb'];
            charts.analyticsDiff = new Chart(diffCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Easy', 'Medium', 'Hard'],
                    datasets: [{
                        data: diffData,
                        backgroundColor: diffColors,
                        borderWidth: 0,
                        cutout: '70%'
                    }]
                },
                options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
            });
        }

        // Analytics Topic Chart
        const topicCtx = document.getElementById('analyticsTopicChart');
        if (topicCtx) {
            if (charts.analyticsTopic) charts.analyticsTopic.destroy();
            const topTopics = Object.entries(topicCounts).sort((a,b)=>b[1]-a[1]).slice(0,5);
            charts.analyticsTopic = new Chart(topicCtx, {
                type: 'bar',
                data: {
                    labels: topTopics.length > 0 ? topTopics.map(t=>t[0]) : ['DSA', 'System Design', 'ML', 'Web Dev', 'Misc'],
                    datasets: [{
                        label: 'Mastery Level',
                        data: topTopics.length > 0 ? topTopics.map(t=>t[1]) : [0, 0, 0, 0, 0],
                        backgroundColor: '#2563eb',
                        borderRadius: 6
                    }]
                },
                options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
            });
        }
    };

    const renderDashboardProgress = () => {
        updateCommandCenter();
        renderSavedPlaylists();
    };

    // Real Resume Analysis uploader logic
    const handleResumeAnalysis = async (file) => {
        const role = document.getElementById('target-role').value.trim() || "Software Engineer";
        const benchmark = document.getElementById('target-benchmark').value;

        // Reset and show loading
        uploadZone.style.display = 'none';
        analysisStatus.style.display = 'block';
        analysisResults.style.display = 'none';
        statusText.textContent = "Uploading and extracting text...";

        const formData = new FormData();
        formData.append('file', file);
        formData.append('role', role);
        formData.append('benchmark', benchmark);

        try {
            // UX progress steps
            const progressSteps = [
                "Simulating ATS scan...",
                "Recruiter is skimming your profile...",
                "Hiring Manager deep-dive evaluation...",
                "Comparing against market competitors...",
                "Finalizing brutal breakdown..."
            ];
            
            let step = 0;
            const progressInt = setInterval(() => {
                if (step < progressSteps.length) {
                    statusText.textContent = progressSteps[step++];
                }
            }, 1800);

            const res = await fetch('/analyze-resume', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInt);

            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || "Analysis failed");
            }

            const data = await res.json();
            
            // Save to in-memory state for dashboard persistence
            latestResumeAnalysis = {
                score: data.final_score * 10 || 85,
                verdict: data.hire_verdict || 'Excellent',
                impact: data.final_score >= 8 ? 'Strong' : 'Average',
                match: data.ats_simulation?.ats_pass_probability || 'High',
                ats: data.ats_simulation?.keyword_match_score || 85
            };

            renderResumeResults(data);

        } catch (err) {
            showToast(err.message);
            uploadZone.style.display = 'block';
        } finally {
            analysisStatus.style.display = 'none';
        }
    };

    const renderResumeResults = (data) => {
        analysisResults.style.display = 'block';
        
        // Final Score & Market Position
        document.getElementById('res-score-value').textContent = `${data.final_score || 0}/10`;
        document.getElementById('res-market').textContent = `Market: ${data.market_positioning || 'N/A'}`;
        
        // Verdict Pill
        const verdictPill = document.getElementById('res-verdict-pill');
        const hireVerdict = data.hire_verdict || 'No Hire';
        verdictPill.textContent = hireVerdict.toUpperCase();
        
        verdictPill.className = 'decision-pill';
        if (hireVerdict.toLowerCase().includes('hire') && !hireVerdict.toLowerCase().includes('no')) {
            verdictPill.classList.add('select');
        } else if (hireVerdict.toLowerCase().includes('borderline')) {
            verdictPill.classList.add('borderline');
        } else {
            verdictPill.classList.add('reject');
        }

        // Section Summaries
        document.getElementById('res-brutal-summary').textContent = data.brutal_analysis?.summary || '';
        document.getElementById('res-risk-text').textContent = data.rejection_risk?.reason || '';

        // Category Table
        const hmTable = document.getElementById('res-hm-table');
        hmTable.innerHTML = '';
        (data.category_breakdown || []).forEach(cat => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${cat.category}</strong></td>
                <td>${cat.weight}</td>
                <td><span class="pill-badge">${cat.score}/10</span></td>
                <td>${cat.reason}</td>
            `;
            hmTable.appendChild(tr);
        });

        // ATS Stage
        document.getElementById('res-ats-match').textContent = `${data.ats_simulation?.keyword_match_score || 0}%`;
        document.getElementById('res-ats-prob').textContent = data.ats_simulation?.ats_pass_probability || 'Low';
        
        const atsMissing = document.getElementById('res-ats-missing');
        atsMissing.innerHTML = '';
        (data.ats_simulation?.missing_critical_keywords || []).forEach(kw => {
            const li = document.createElement('li');
            li.style.listStyle = 'none';
            li.innerHTML = `<span class="pill-badge" style="background:var(--danger-light); color:var(--danger);">${escapeHTML(kw)}</span>`;
            atsMissing.appendChild(li);
        });

        // Recruiter Stage
        document.getElementById('res-recruiter-impression').textContent = `"${data.recruiter_snap_judgment?.first_impression || ''}"`;
        const recruiterReasons = document.getElementById('res-recruiter-reasons');
        recruiterReasons.innerHTML = '';
        (data.recruiter_snap_judgment?.top_reasons || []).forEach(r => {
            const li = document.createElement('li');
            li.textContent = r;
            recruiterReasons.appendChild(li);
        });

        // What Works
        const worksList = document.getElementById('res-works-list');
        worksList.innerHTML = '';
        (data.what_works || []).forEach(w => {
            const li = document.createElement('li');
            li.textContent = w;
            worksList.appendChild(li);
        });

        // Action Projects
        const actionProjects = document.getElementById('res-action-projects');
        actionProjects.innerHTML = '';
        (data.action_plan?.project_ideas || []).forEach(p => {
            const div = document.createElement('div');
            div.className = 'action-box';
            div.innerHTML = `
                <h6 style="font-weight:700; font-size:0.85rem; margin-bottom:4px;">${escapeHTML(p.title)}</h6>
                <p style="font-size:0.75rem; color:var(--text-sub); margin-bottom:4px;"><strong>Stack:</strong> ${escapeHTML(p.stack)}</p>
                <p style="font-size:0.75rem; color:var(--text-sub);">${escapeHTML(p.description)}</p>
            `;
            actionProjects.appendChild(div);
        });

        // Action Tools
        const actionTools = document.getElementById('res-action-tools');
        actionTools.innerHTML = '';
        (data.action_plan?.tools_to_learn || []).forEach(t => {
            const li = document.createElement('li');
            li.textContent = t;
            actionTools.appendChild(li);
        });

        // Rewrite Examples
        const rewritesContainer = document.getElementById('res-action-rewrites');
        rewritesContainer.innerHTML = '';
        (data.action_plan?.bullet_rewrites || []).forEach(ex => {
            const item = document.createElement('div');
            item.className = 'rewrite-item';
            item.innerHTML = `
                <div class="rewrite-new">Improved: "${escapeHTML(ex.improved)}"</div>
                <div class="rewrite-orig">From: "${escapeHTML(ex.original)}"</div>
            `;
            rewritesContainer.appendChild(item);
        });

        showToast('Multi-stage analysis complete!');
    };

    // Event Listeners for Category Selection (Practice page)
    if (btnDsaCategory) btnDsaCategory.addEventListener('click', enterDsaPrep);
    if (btnResumeCategory) btnResumeCategory.addEventListener('click', enterResumeAnalyzer);
    if (backToCategoriesDsa) backToCategoriesDsa.addEventListener('click', showSelectionScreen);
    if (backToCategoriesResume) backToCategoriesResume.addEventListener('click', showSelectionScreen);

    // Resume Upload Events
    btnTriggerUpload.addEventListener('click', () => resumeUpload.click());
    resumeUpload.addEventListener('change', (e) => {
        if (e.target.files.length > 0) handleResumeAnalysis(e.target.files[0]);
    });

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) handleResumeAnalysis(e.dataTransfer.files[0]);
    });

    companySearchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const filtered = allCompanies.filter(c => c.toLowerCase().includes(term));
        renderCompanies(filtered);
    });

    backToCompanies.addEventListener('click', () => {
        questionsView.style.display = 'none';
        companySelection.style.display = 'block';
    });

    // Event Listeners for search/forms
    ctaButton.addEventListener('click', handleSearch);
    skillInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });

    tabPlaylists.addEventListener('click', () => renderStep('playlists'));
    tabCertificates.addEventListener('click', () => renderStep('certificates'));
    tabRoadmap.addEventListener('click', () => renderStep('roadmap'));

    // ── Student Projects Management ──
    const projectsListContainer = document.getElementById('projects-list-container');
    const addProjectForm = document.getElementById('add-project-form');

    const defaultProjects = [
        { title: "Distributed Rate Limiter", category: "Backend", desc: "Build an API rate limiter service in Go/Python utilizing Redis token bucket algorithm." },
        { title: "Realtime Collaborative Editor", category: "Fullstack", desc: "Create a dynamic text editor using WebSockets and Operational Transformation patterns." }
    ];

    let customProjects = [];

    const loadProjects = async () => {
        try {
            const res = await fetch('/get-user-projects');
            if (res.ok) {
                const list = await res.json();
                if (Array.isArray(list)) {
                    customProjects = list;
                }
            }
        } catch (e) {
            console.error("Failed to load custom projects:", e);
        }
        renderProjectsList();
    };

    const renderProjectsList = () => {
        if (!projectsListContainer) return;
        projectsListContainer.innerHTML = '';

        // Render recommended blueprints
        defaultProjects.forEach(p => {
            const card = document.createElement('div');
            card.className = 'card show';
            card.innerHTML = `
                <div class="card-header">
                    <span class="pill-badge" style="background:var(--primary-light); color:var(--primary); font-weight:700;">${escapeHTML(p.category)}</span>
                </div>
                <h3 class="card-title" style="margin-top:8px;">${escapeHTML(p.title)}</h3>
                <p class="card-desc" style="margin-bottom:0;">${escapeHTML(p.desc)}</p>
            `;
            projectsListContainer.appendChild(card);
        });

        // Render student's custom projects
        customProjects.forEach((p, idx) => {
            const card = document.createElement('div');
            card.className = 'card show';
            card.innerHTML = `
                <div class="card-header">
                    <span class="pill-badge" style="background:var(--success-light); color:var(--success); font-weight:700;">${escapeHTML(p.category)}</span>
                    <button class="btn-back btn-delete-project" data-index="${idx}" style="margin-left:auto; padding:2px 8px; color:var(--danger); border-color:rgba(239,68,68,0.2); background:var(--danger-light); font-size:0.75rem;">Delete</button>
                </div>
                <h3 class="card-title" style="margin-top:8px;">${escapeHTML(p.title)}</h3>
                <p class="card-desc" style="margin-bottom:0;">${escapeHTML(p.desc)}</p>
            `;
            projectsListContainer.appendChild(card);
        });

        // Add event listeners to delete buttons
        document.querySelectorAll('.btn-delete-project').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const index = parseInt(e.target.getAttribute('data-index'));
                customProjects.splice(index, 1);
                await syncProjects();
                renderProjectsList();
            });
        });
    };

    const syncProjects = async () => {
        try {
            await fetch('/sync-user-projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ projects_list: customProjects })
            });
        } catch (e) {
            console.error("Failed to sync custom projects:", e);
        }
    };

    if (addProjectForm) {
        addProjectForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('project-title').value.trim();
            const category = document.getElementById('project-category').value.trim();
            const desc = document.getElementById('project-desc').value.trim();

            if (!title || !category || !desc) return;

            customProjects.push({ title, category, desc });
            addProjectForm.reset();

            await syncProjects();
            renderProjectsList();
            showToast('✅ Project added successfully!');
        });
    }

    // ── Sidebar Router Logic ──────────────────────────────────────
    const navItems = document.querySelectorAll('.sidebar .nav-item');
    const views = document.querySelectorAll('.content-view');

    const switchView = (targetViewId) => {
        views.forEach(v => {
            v.classList.remove('active');
            if (v.id === targetViewId) {
                v.classList.add('active');
            }
        });

        // Trigger view-specific dynamic logic
        if (targetViewId === 'view-dashboard') {
            renderDashboardProgress();
        } else if (targetViewId === 'view-practice') {
            enterDsaPrep();
        } else if (targetViewId === 'view-resume') {
            enterResumeAnalyzer();
        } else if (targetViewId === 'view-learning') {
            resetViews();
            document.getElementById('view-learning').classList.add('active');
            emptyState.style.display = 'block';
        } else if (targetViewId === 'view-analytics') {
            renderAnalyticsCharts();
        } else if (targetViewId === 'view-projects') {
            loadProjects();
        }
    };

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
            
            const targetViewId = item.getAttribute('data-view');
            switchView(targetViewId);
        });
    });

    // Dashboard Buttons Action Link
    document.getElementById('dashboard-improve-resume-btn').addEventListener('click', () => {
        const resumeTabBtn = document.getElementById('btn-sidebar-resume');
        if (resumeTabBtn) resumeTabBtn.click();
    });

    document.getElementById('dashboard-view-calendar-btn').addEventListener('click', () => {
        const interviewTabBtn = document.getElementById('btn-sidebar-interviews');
        if (interviewTabBtn) interviewTabBtn.click();
    });

    // AI Recommendations Auto Search click triggers
    const triggerRecommendationSearch = (skillName) => {
        const learningTabBtn = document.getElementById('btn-sidebar-learning');
        if (learningTabBtn) {
            learningTabBtn.click();
            skillInput.value = skillName;
            handleSearch();
        }
    };

    document.getElementById('rec-item-graphs').addEventListener('click', () => {
        triggerRecommendationSearch('Graph Algorithms');
    });

    document.getElementById('rec-item-sysdesign').addEventListener('click', () => {
        triggerRecommendationSearch('System Design');
    });

    // ── Dedicated AI Mentor page consultation ────────────────────
    const mentorSubmitPage = document.getElementById('mentor-submit-btn-page');
    const mentorResultPage = document.getElementById('mentor-result-page');

    if (mentorSubmitPage) {
        mentorSubmitPage.addEventListener('click', async () => {
            const goal = document.getElementById('mentor-goal-page').value.trim();
            const skills = document.getElementById('mentor-skills-page').value.trim();
            if (!goal) { mentorResultPage.innerHTML = '<p style="color:#f97316">Please enter your career goal.</p>'; return; }

            mentorSubmitPage.textContent = 'Consulting your mentor...';
            mentorSubmitPage.disabled = true;
            mentorResultPage.innerHTML = '<div style="text-align:center; padding:20px;"><div class="spinner"></div><p style="color:var(--text-sub);">⚡ Analyzing your path...</p></div>';

            try {
                const res = await fetch('/mentor-mode', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ goal, current_skills: skills })
                });
                const data = await res.json();
                if (data.error) throw new Error(data.error);

                mentorResultPage.innerHTML = `
                    <div style="border-top:1px solid var(--border); padding-top:16px; margin-top:20px;">
                        <p style="color:#f97316; font-weight:700; font-size:1.05rem; margin-bottom:12px;">
                            "${escapeHTML(data.verdict)}"
                        </p>
                        ${ data.wasted_time && data.wasted_time.length ? `
                        <p style="color:var(--text-sub); font-size:0.85rem; margin-bottom:4px; font-weight:600;">⛔ Stop wasting time on:</p>
                        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;">
                            ${data.wasted_time.map(s => `<span class="pill-badge" style="background:#fee2e2;color:#ef4444;border-color:transparent;">${escapeHTML(s)}</span>`).join('')}
                        </div>` : ''}
                        ${ data.must_learn_now && data.must_learn_now.length ? `
                        <p style="color:var(--text-sub); font-size:0.85rem; margin-bottom:6px; font-weight:600;">✅ Learn these NOW:</p>
                        <ul style="padding-left:16px; color:var(--text-main); font-size:0.85rem; margin-bottom:12px;">
                            ${data.must_learn_now.map(i => `<li><strong>${escapeHTML(i.skill)}</strong> — ${escapeHTML(i.reason)}</li>`).join('')}
                        </ul>` : ''}
                        <p style="color:var(--text-sub); font-size:0.85rem; line-height:1.6; margin-bottom:12px;">
                            ${escapeHTML(data.brutal_truth)}
                        </p>
                        <div style="background:var(--primary-light); border-left:3px solid var(--primary); padding:12px 16px; border-radius:8px;">
                            <p style="color:var(--primary); font-size:0.85rem; margin:0; font-weight:600;">🎯 This week: ${escapeHTML(data.action_this_week)}</p>
                        </div>
                    </div>
                `;
            } catch(e) {
                mentorResultPage.innerHTML = `<p style="color:var(--danger);">Failed: ${escapeHTML(e.message)}</p>`;
            } finally {
                mentorSubmitPage.textContent = 'Get Brutal Advice ⚡';
                mentorSubmitPage.disabled = false;
            }
        });
    }

    // Set Welcome back title initials and text
    const updateWelcomeMessage = async () => {
        try {
            const res = await fetch('/get-user-session');
            if (res.ok) {
                const data = await res.json();
                if (data.logged_in) {
                    let name = data.name;
                    name = name.charAt(0).toUpperCase() + name.slice(1);
                    document.getElementById('welcome-title-banner').textContent = `Welcome back, ${name}! 👋`;
                    document.getElementById('user-avatar-initials').textContent = name.substring(0, 2).toUpperCase();
                    return;
                }
            }
        } catch (e) {
            console.error("Failed to fetch user session:", e);
        }

        const storedUser = sessionStorage.getItem('logged_in_user_email') || 'Learner';
        let name = storedUser.split('@')[0];
        name = name.charAt(0).toUpperCase() + name.slice(1);
        
        document.getElementById('welcome-title-banner').textContent = `Welcome back, ${name}! 👋`;
        document.getElementById('user-avatar-initials').textContent = name.substring(0, 2).toUpperCase();
    };

    const initDsaProgress = async () => {
        try {
            const res = await fetch('/get-dsa-progress');
            if (res.ok) {
                const list = await res.json();
                if (Array.isArray(list)) {
                    solvedDsaQuestions = list;
                }
            }
        } catch (e) {
            console.error("Failed to fetch DSA progress from DB:", e);
        }
        renderDashboardProgress();
    };

    // Initial render call
    updateWelcomeMessage();
    initDsaProgress();
    initSavedPlaylists();

    // Expose trackClick globally for inline onclick handlers
    window.trackClickGlobal = (url, title) => trackClick(url, title, 'click');
});
