import { useState, useRef, useCallback } from "react";
import "./App.css";
import axios from "axios";
import { Upload, Image, Clock, Film, X, Download, Loader2, GripVertical, ChevronUp, ChevronDown, Volume2, VolumeX, User, UserRound, Music, Zap, Mail } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const LOGO_URL = "https://customer-assets.emergentagent.com/job_51b47bd8-e504-4aa6-94b4-6cf45232979c/artifacts/qtrcbtm8_logo%20ar%20sans%20arreire%20plan.png";

function App() {
  const [images, setImages] = useState([]);
  const [subtitles, setSubtitles] = useState([]);
  const [duration, setDuration] = useState(5);
  const [enableVoiceover, setEnableVoiceover] = useState(false);
  const [voiceGender, setVoiceGender] = useState("male");
  const [hdQuality, setHdQuality] = useState(false);
  const [backgroundMusic, setBackgroundMusic] = useState(null);
  const [transitionType, setTransitionType] = useState("zoomin");
  const [ultraFastMode, setUltraFastMode] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState("");
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);
  const fileInputRef = useRef(null);
  const pollingRef = useRef(null);
  const wakeLockRef = useRef(null);
  const [currentProjectId, setCurrentProjectId] = useState(null);

  const handleFiles = useCallback((files) => {
    const validFiles = Array.from(files).filter(file =>
      file.type.startsWith('image/')
    ).slice(0, 20 - images.length);
    
    if (validFiles.length > 0) {
      setImages(prev => [...prev, ...validFiles]);
      setSubtitles(prev => [...prev, ...validFiles.map(() => "")]);
    }
  }, [images.length]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    if (draggedIndex === null) {
      handleFiles(e.dataTransfer.files);
    }
  }, [handleFiles, draggedIndex]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    if (draggedIndex === null) {
      setIsDragging(true);
    }
  }, [draggedIndex]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const removeImage = (index) => {
    setImages(prev => prev.filter((_, i) => i !== index));
    setSubtitles(prev => prev.filter((_, i) => i !== index));
  };

  const updateSubtitle = (index, value) => {
    setSubtitles(prev => {
      const newSubtitles = [...prev];
      newSubtitles[index] = value;
      return newSubtitles;
    });
  };

  const handleImageDragStart = (e, index) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', index.toString());
  };

  const handleImageDragOver = (e, index) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (draggedIndex !== null && draggedIndex !== index) {
      setDragOverIndex(index);
    }
  };

  const handleImageDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleImageDrop = (e, dropIndex) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }

    const newImages = [...images];
    const newSubtitles = [...subtitles];
    
    const [draggedImage] = newImages.splice(draggedIndex, 1);
    const [draggedSubtitle] = newSubtitles.splice(draggedIndex, 1);
    
    newImages.splice(dropIndex, 0, draggedImage);
    newSubtitles.splice(dropIndex, 0, draggedSubtitle);
    
    setImages(newImages);
    setSubtitles(newSubtitles);
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleImageDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const moveImage = (index, direction) => {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= images.length) return;
    
    const newImages = [...images];
    const newSubtitles = [...subtitles];
    
    [newImages[index], newImages[newIndex]] = [newImages[newIndex], newImages[index]];
    [newSubtitles[index], newSubtitles[newIndex]] = [newSubtitles[newIndex], newSubtitles[index]];
    
    setImages(newImages);
    setSubtitles(newSubtitles);
  };

  // Wake Lock to prevent device sleep
  const requestWakeLock = async () => {
    try {
      if ('wakeLock' in navigator) {
        wakeLockRef.current = await navigator.wakeLock.request('screen');
        console.log('Wake Lock activated');
      }
    } catch (err) {
      console.error('Wake Lock error:', err);
    }
  };

  const releaseWakeLock = async () => {
    if (wakeLockRef.current) {
      try {
        await wakeLockRef.current.release();
        wakeLockRef.current = null;
        console.log('Wake Lock released');
      } catch (err) {
        console.error('Wake Lock release error:', err);
      }
    }
  };

  const pollStatus = async (projectId) => {
    try {
      const response = await axios.get(`${API}/project/${projectId}`);
      const { status, progress, progress_message, video_url, error_message } = response.data;
      
      setProgress(progress);
      setProgressMessage(progress_message);

      if (status === "completed") {
        setVideoUrl(`${BACKEND_URL}${video_url}`);
        setIsGenerating(false);
        setCurrentProjectId(null);
        await releaseWakeLock();
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      } else if (status === "error") {
        setError(error_message || "Une erreur est survenue");
        setIsGenerating(false);
        setCurrentProjectId(null);
        await releaseWakeLock();
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      } else if (status === "cancelled") {
        setError("Génération annulée");
        setIsGenerating(false);
        setCurrentProjectId(null);
        await releaseWakeLock();
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
      }
    } catch (err) {
      console.error("Polling error:", err);
      if (pollingRef.current && Date.now() - pollingRef.startTime > 180000) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
        setError("La génération prend trop de temps. Veuillez réessayer.");
        setIsGenerating(false);
        setCurrentProjectId(null);
        await releaseWakeLock();
      }
    }
  };

  const cancelGeneration = async () => {
    if (!currentProjectId) return;
    
    try {
      await axios.delete(`${API}/project/${currentProjectId}`);
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      setIsGenerating(false);
      setCurrentProjectId(null);
      setProgress(0);
      setProgressMessage("");
      await releaseWakeLock();
    } catch (err) {
      console.error("Cancel error:", err);
    }
  };

  const generateVideo = async () => {
    if (images.length === 0) return;
    
    setIsGenerating(true);
    setProgress(0);
    setProgressMessage("Envoi des images...");
    setVideoUrl(null);
    setError(null);

    // Activate Wake Lock
    await requestWakeLock();

    const formData = new FormData();
    images.forEach((image) => {
      formData.append("images", image);
    });
    formData.append("subtitles", JSON.stringify(subtitles));
    formData.append("duration_per_image", duration.toString());
    formData.append("enable_voiceover", enableVoiceover.toString());
    formData.append("voice_gender", voiceGender);
    formData.append("hd_quality", hdQuality.toString());
    formData.append("transition_type", transitionType);
    formData.append("ultra_fast_mode", ultraFastMode.toString());
    if (backgroundMusic) {
      formData.append("background_music", backgroundMusic);
    }
    if (userEmail) {
      formData.append("user_email", userEmail);
    }

    try {
      const response = await axios.post(`${API}/create-video`, formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });
      
      const { project_id } = response.data;
      setCurrentProjectId(project_id);
      pollingRef.current = setInterval(() => pollStatus(project_id), 1000);
      pollingRef.startTime = Date.now();
    } catch (err) {
      setError(err.response?.data?.detail || "Erreur lors de la génération");
      setIsGenerating(false);
      setCurrentProjectId(null);
      await releaseWakeLock();
    }
  };

  const resetForm = async () => {
    setImages([]);
    setSubtitles([]);
    setVideoUrl(null);
    setError(null);
    setProgress(0);
    setProgressMessage("");
    setEnableVoiceover(false);
    setVoiceGender("male");
    setHdQuality(false);
    setBackgroundMusic(null);
    setTransitionType("zoomin");
    setCurrentProjectId(null);
    setUserEmail("");
    await releaseWakeLock();
  };

  return (
    <div className="app-container" data-testid="app-container">
      {/* Header */}
      <header className="header" data-testid="header">
        <div className="header-content">
          <div className="header-left">
            <Film className="film-icon" />
            <div className="header-text">
              <h1 className="header-title">Afrique Résurrection</h1>
              <p className="header-subtitle">Générateur de Vidéos HD Automatique</p>
            </div>
          </div>
          <img src={LOGO_URL} alt="Afrique Résurrection" className="header-logo" data-testid="header-logo" />
        </div>
      </header>

      {/* Main Content */}
      <main className="main-content">
        {/* Hero Section */}
        <section className="hero-section" data-testid="hero-section">
          <h2 className="hero-title">Transformez vos photos en vidéos HD captivantes</h2>
          <p className="hero-description">
            Créez facilement des diaporamas vidéo professionnels en qualité HD avec effet Ken Burns, sous-titres personnalisés et transitions fluides. Vos images seront automatiquement améliorées pour une qualité optimale.
          </p>
        </section>

        {/* Features */}
        <section className="features-section" data-testid="features-section">
          <div className="feature-card">
            <div className="feature-badge">1</div>
            <Image className="feature-icon" />
            <h3 className="feature-title">Qualité HD</h3>
            <p className="feature-description">Images optimisées automatiquement</p>
          </div>
          <div className="feature-card">
            <div className="feature-badge">2</div>
            <Clock className="feature-icon" />
            <h3 className="feature-title">Durée personnalisée</h3>
            <p className="feature-description">2 à 10 secondes par image</p>
          </div>
          <div className="feature-card">
            <div className="feature-badge">3</div>
            <Film className="feature-icon" />
            <h3 className="feature-title">Vidéo MP4 HD</h3>
            <p className="feature-description">Format 1080x1920 vertical</p>
          </div>
        </section>

        {/* Upload Zone */}
        {!videoUrl && (
          <section className="upload-section" data-testid="upload-section">
            <div
              className={`upload-zone ${isDragging ? 'dragging' : ''} ${images.length > 0 ? 'has-images' : ''}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => images.length === 0 && fileInputRef.current?.click()}
              data-testid="upload-zone"
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={(e) => handleFiles(e.target.files)}
                accept="image/*"
                multiple
                hidden
                data-testid="file-input"
              />
              
              {images.length === 0 ? (
                <div className="upload-placeholder">
                  <Upload className="upload-icon" />
                  <p className="upload-text">Cliquez ou glissez vos images ici</p>
                  <p className="upload-hint">JPG, PNG, GIF, WebP acceptés • Max 20 images • Optimisation HD automatique</p>
                </div>
              ) : (
                <div className="images-container">
                  <div className="reorder-hint">
                    <GripVertical size={16} />
                    <span>Glissez les images pour réorganiser l'ordre • Qualité HD garantie</span>
                  </div>
                  <div className="images-grid">
                    {images.map((image, index) => (
                      <div
                        key={index}
                        className={`image-item ${draggedIndex === index ? 'dragging' : ''} ${dragOverIndex === index ? 'drag-over' : ''}`}
                        draggable
                        onDragStart={(e) => handleImageDragStart(e, index)}
                        onDragOver={(e) => handleImageDragOver(e, index)}
                        onDragLeave={handleImageDragLeave}
                        onDrop={(e) => handleImageDrop(e, index)}
                        onDragEnd={handleImageDragEnd}
                        data-testid={`image-item-${index}`}
                      >
                        <div className="image-preview">
                          <img src={URL.createObjectURL(image)} alt={`Preview ${index + 1}`} />
                          <div className="image-controls">
                            <button
                              className="move-btn"
                              onClick={(e) => { e.stopPropagation(); moveImage(index, -1); }}
                              disabled={index === 0}
                              title="Monter"
                              data-testid={`move-up-${index}`}
                            >
                              <ChevronUp size={16} />
                            </button>
                            <button
                              className="move-btn"
                              onClick={(e) => { e.stopPropagation(); moveImage(index, 1); }}
                              disabled={index === images.length - 1}
                              title="Descendre"
                              data-testid={`move-down-${index}`}
                            >
                              <ChevronDown size={16} />
                            </button>
                          </div>
                          <button
                            className="remove-btn"
                            onClick={(e) => { e.stopPropagation(); removeImage(index); }}
                            data-testid={`remove-image-${index}`}
                          >
                            <X size={16} />
                          </button>
                          <span className="image-number">{index + 1}</span>
                          <div className="drag-handle" title="Glisser pour réorganiser">
                            <GripVertical size={18} />
                          </div>
                        </div>
                        <input
                          type="text"
                          placeholder="Sous-titre (optionnel)"
                          value={subtitles[index] || ""}
                          onChange={(e) => updateSubtitle(index, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="subtitle-input"
                          data-testid={`subtitle-input-${index}`}
                        />
                      </div>
                    ))}
                    {images.length < 20 && (
                      <div
                        className="add-more-btn"
                        onClick={(e) => { e.stopPropagation(); fileInputRef.current?.click(); }}
                        data-testid="add-more-images"
                      >
                        <Upload size={24} />
                        <span>Ajouter</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Duration Slider */}
            {images.length > 0 && (
              <div className="duration-section" data-testid="duration-section">
                <label className="duration-label">
                  Durée par image: <strong>{duration}s</strong>
                </label>
                <input
                  type="range"
                  min="2"
                  max="10"
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="duration-slider"
                  data-testid="duration-slider"
                />
                <div className="duration-marks">
                  <span>2s</span>
                  <span>10s</span>
                </div>
              </div>
            )}

            {/* Voiceover Toggle */}
            {images.length > 0 && !ultraFastMode && (
              <div className="voiceover-section voiceover-highlight" data-testid="voiceover-section">
                <div
                  className={`voiceover-toggle ${enableVoiceover ? 'active' : ''}`}
                  onClick={() => setEnableVoiceover(!enableVoiceover)}
                  data-testid="voiceover-toggle"
                >
                  <div className="voiceover-info">
                    {enableVoiceover ? (
                      <Volume2 className="voiceover-icon" />
                    ) : (
                      <VolumeX className="voiceover-icon" />
                    )}
                    <div className="voiceover-text">
                      <h4>Voix off professionnelle 🎤</h4>
                      <p>Lecture audio des sous-titres en français (ACTIVEZ POUR ENTENDRE)</p>
                    </div>
                  </div>
                  <div className={`toggle-switch ${enableVoiceover ? 'active' : ''}`} />
                </div>
                
                {/* Voice Gender Selector */}
                {enableVoiceover && (
                  <div className="voice-gender-section" data-testid="voice-gender-section">
                    <p className="voice-gender-label">Choisir la voix :</p>
                    <div className="voice-gender-options">
                      <button
                        className={`voice-option ${voiceGender === 'male' ? 'active' : ''}`}
                        onClick={() => setVoiceGender('male')}
                        data-testid="voice-male-btn"
                      >
                        <User size={20} />
                        <span>Homme</span>
                      </button>
                      <button
                        className={`voice-option ${voiceGender === 'female' ? 'active' : ''}`}
                        onClick={() => setVoiceGender('female')}
                        data-testid="voice-female-btn"
                      >
                        <UserRound size={20} />
                        <span>Femme</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* HD Quality Toggle */}
            {images.length > 0 && !ultraFastMode && (
              <div className="voiceover-section" data-testid="hd-section" style={{marginTop: '1rem'}}>
                <div
                  className={`voiceover-toggle ${hdQuality ? 'active' : ''}`}
                  onClick={() => setHdQuality(!hdQuality)}
                  data-testid="hd-toggle"
                >
                  <div className="voiceover-info">
                    <Film className="voiceover-icon" />
                    <div className="voiceover-text">
                      <h4>Qualité HD (Plus lent)</h4>
                      <p>Upscaling et amélioration avancée des images</p>
                    </div>
                  </div>
                  <div className={`toggle-switch ${hdQuality ? 'active' : ''}`} />
                </div>
              </div>
            )}

            {/* Background Music Selector */}
            {images.length > 0 && !ultraFastMode && (
              <div className="voiceover-section" data-testid="music-section" style={{marginTop: '1rem'}}>
                <div className="music-header">
                  <Music className="voiceover-icon" style={{color: '#F97316'}} />
                  <h4 style={{margin: 0, fontSize: '1rem', fontWeight: 600, color: '#111827'}}>Musique de fond (optionnel)</h4>
                </div>
                <div className="music-options">
                  <button
                    className={`music-option ${backgroundMusic === null ? 'active' : ''}`}
                    onClick={() => setBackgroundMusic(null)}
                    data-testid="music-none-btn"
                  >
                    <VolumeX size={20} />
                    <span>Sans musique</span>
                  </button>
                  <button
                    className={`music-option ${backgroundMusic === 'afrique_resurrection' ? 'active' : ''}`}
                    onClick={() => setBackgroundMusic('afrique_resurrection')}
                    data-testid="music-afrique-btn"
                  >
                    <Music size={20} />
                    <span>Afrique Résurrection</span>
                  </button>
                  <button
                    className={`music-option ${backgroundMusic === 'breaking_news' ? 'active' : ''}`}
                    onClick={() => setBackgroundMusic('breaking_news')}
                    data-testid="music-breaking-btn"
                  >
                    <Music size={20} />
                    <span>Breaking News</span>
                  </button>
                </div>
              </div>
            )}

            {/* Transition Type Selector */}
            {images.length > 0 && !ultraFastMode && (
              <div className="voiceover-section" data-testid="transition-section" style={{marginTop: '1rem'}}>
                <div className="music-header">
                  <Film className="voiceover-icon" style={{color: '#F97316'}} />
                  <h4 style={{margin: 0, fontSize: '1rem', fontWeight: 600, color: '#111827'}}>Type de transition</h4>
                </div>
                <div className="music-options">
                  <button
                    className={`music-option ${transitionType === 'zoomin' ? 'active' : ''}`}
                    onClick={() => setTransitionType('zoomin')}
                    data-testid="transition-zoomin-btn"
                  >
                    <Film size={20} />
                    <span>Zoom In + Whoosh</span>
                  </button>
                  <button
                    className={`music-option ${transitionType === 'fade' ? 'active' : ''}`}
                    onClick={() => setTransitionType('fade')}
                    data-testid="transition-fade-btn"
                  >
                    <Image size={20} />
                    <span>Fondu</span>
                  </button>
                </div>
              </div>
            )}

            {/* Ultra Fast Mode Toggle */}
            {images.length > 0 && (
              <div className="voiceover-section" style={{marginTop: '1rem', background: ultraFastMode ? 'linear-gradient(135deg, #FFF7ED 0%, #FFEDD5 100%)' : 'transparent', border: ultraFastMode ? '2px solid #F97316' : 'none'}}>
                <div
                  className={`voiceover-toggle ${ultraFastMode ? 'active' : ''}`}
                  onClick={() => {
                    const newMode = !ultraFastMode;
                    setUltraFastMode(newMode);
                    if (newMode) {
                      // Désactiver les options incompatibles
                      setEnableVoiceover(false);
                      setBackgroundMusic(null);
                      setHdQuality(false);
                    }
                  }}
                  data-testid="ultrafast-toggle"
                >
                  <div className="voiceover-info">
                    <Zap className="voiceover-icon" style={{color: ultraFastMode ? '#F97316' : '#6B7280'}} />
                    <div className="voiceover-text">
                      <h4 style={{color: ultraFastMode ? '#F97316' : '#111827'}}>⚡ Mode Ultra Rapide</h4>
                      <p style={{fontSize: '0.85rem'}}>
                        {ultraFastMode ? 
                          "Génération 3x plus rapide - Sous-titres + Logo uniquement" : 
                          "Désactive : transitions, musique, voix off (génération 3x plus rapide)"
                        }
                      </p>
                    </div>
                  </div>
                  <div className={`toggle-switch ${ultraFastMode ? 'active' : ''}`} />
                </div>
              </div>
            )}

            {/* Email notification */}
            {images.length > 0 && (
              <div className="voiceover-section" style={{marginTop: '1rem'}}>
                <div className="music-header">
                  <Mail className="voiceover-icon" style={{color: '#F97316'}} />
                  <h4 style={{margin: 0, fontSize: '1rem', fontWeight: 600, color: '#111827'}}>Recevoir le lien par email (optionnel)</h4>
                </div>
                <input
                  type="email"
                  placeholder="votre@email.com"
                  value={userEmail}
                  onChange={(e) => setUserEmail(e.target.value)}
                  className="subtitle-input"
                  style={{borderRadius: '0.5rem', border: '2px solid #e5e7eb', marginTop: '0.5rem'}}
                  data-testid="email-input"
                />
              </div>
            )}

            {/* Generate Button */}
            {images.length > 0 && !isGenerating && (
              <button
                className="generate-btn"
                onClick={generateVideo}
                data-testid="generate-btn"
                style={{background: ultraFastMode ? 'linear-gradient(135deg, #F97316 0%, #EA580C 100%)' : undefined}}
              >
                {ultraFastMode ? <Zap size={20} /> : <Film size={20} />}
                {ultraFastMode ? 
                  `⚡ Génération Ultra Rapide (${images.length} image${images.length > 1 ? 's' : ''})` :
                  `Générer la vidéo ${hdQuality ? 'HD' : ''} (${images.length} image${images.length > 1 ? 's' : ''})`
                }
              </button>
            )}

            {/* Progress */}
            {isGenerating && (
              <div className="progress-section" data-testid="progress-section">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{width: `${progress}%`}}
                  />
                </div>
                <div className="progress-info">
                  <Loader2 className="spinner" />
                  <span>{progressMessage || "Génération en cours..."}</span>
                  <span className="progress-percent">{progress}%</span>
                </div>
                <button
                  className="cancel-btn"
                  onClick={cancelGeneration}
                  data-testid="cancel-btn"
                >
                  <X size={20} />
                  Annuler la génération
                </button>
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="error-message" data-testid="error-message">
                <p>{error}</p>
                <button onClick={() => setError(null)}>Réessayer</button>
              </div>
            )}
          </section>
        )}

        {/* Video Result */}
        {videoUrl && (
          <section className="result-section" data-testid="result-section">
            <h3 className="result-title">Votre vidéo HD est prête ! 🎉</h3>
            <div className="video-container">
              <video
                src={videoUrl}
                controls
                autoPlay
                className="result-video"
                data-testid="result-video"
              />
            </div>
            <div className="result-actions">
              <a
                href={videoUrl}
                download
                className="download-btn"
                data-testid="download-btn"
              >
                <Download size={20} />
                Télécharger la vidéo HD
              </a>
              <button
                className="new-video-btn"
                onClick={resetForm}
                data-testid="new-video-btn"
              >
                Créer une nouvelle vidéo
              </button>
            </div>
          </section>
        )}
      </main>

      {/* Footer */}
      <footer className="footer">
        <div className="footer-content">
          <p className="copyright">© Afrique Résurrection 2026 - Tous droits réservés</p>
          <a href="https://app.emergent.sh/?utm_source=emergent-badge" target="_blank" rel="noopener noreferrer" className="emergent-badge">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M15.5702 8.13142C15.7729 8.0412 16.0007 8.18878 15.9892 8.4103C15.8374 11.3192 14.0965 14.0405 11.2531 15.3065C8.40964 16.5725 5.2224 16.0453 2.95912 14.2117C2.78676 14.072 2.82955 13.804 3.03219 13.7137L4.95677 12.8568C5.04866 12.8159 5.15446 12.823 5.24204 12.8725C6.73377 13.7153 8.59176 13.8649 10.2772 13.1145C11.9626 12.3641 13.0947 10.8833 13.4665 9.21075C13.4883 9.11256 13.5539 9.02918 13.6457 8.98827L15.5702 8.13142Z" fill="white"/>
              <path fillRule="evenodd" clipRule="evenodd" d="M15.3066 4.74698L15.5067 5.19653C15.5759 5.35178 15.5061 5.53366 15.3508 5.60278L1.29992 11.8586C1.14467 11.9278 0.962794 11.8579 0.893675 11.7027L0.701732 11.2716L0.693457 11.2531C-1.10317 7.21778 0.711626 2.49007 4.74692 0.693443C8.78221 -1.10318 13.51 0.711693 15.3066 4.74698ZM2.82356 8.55367C2.63552 8.63739 2.41991 8.51617 2.40853 8.31065C2.28373 6.05724 3.53858 3.85787 5.72286 2.88536C7.90715 1.91286 10.3813 2.45199 11.9724 4.05256C12.1175 4.19854 12.0633 4.43988 11.8753 4.5236L2.82356 8.55367Z" fill="white"/>
            </svg>
            Made with Emergent
          </a>
        </div>
      </footer>
    </div>
  );
}

export default App;
