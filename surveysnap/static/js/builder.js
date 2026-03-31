(function () {
    const bootstrapNode = document.getElementById("builder-bootstrap");
    const root = document.querySelector(".builder-shell");

    if (!bootstrapNode || !root) {
        return;
    }

    const QUESTION_LABELS = {
        short_answer: "Short Answer",
        paragraph: "Paragraph",
        multiple_choice: "Multiple Choice",
        checkboxes: "Checkboxes",
        dropdown: "Dropdown",
        date: "Date",
        rating: "Rating",
        file_upload: "File Upload",
    };

    const QUESTION_ICONS = {
        short_answer: "bi-input-cursor-text",
        paragraph: "bi-text-paragraph",
        multiple_choice: "bi-ui-radios",
        checkboxes: "bi-check2-square",
        dropdown: "bi-menu-button-wide",
        date: "bi-calendar3",
        rating: "bi-star",
        file_upload: "bi-cloud-arrow-up",
    };

    const DEFAULT_OPTIONS = ["Option 1", "Option 2"];

    class SurveyBuilderApp {
        constructor(rootNode, bootstrapData) {
            this.root = rootNode;
            this.bootstrap = bootstrapData;
            this.dragQuestionId = null;
            this.activeCanvasPointer = null;
            this.autosaveTimer = null;
            this.localPersistTimer = null;
            this.toastTimerIds = new WeakMap();
            this.isDirty = false;
            this.isSaving = false;
            this.state = this.buildInitialState(bootstrapData);
            this.cacheElements();
            this.bindEvents();
            this.render();
            this.startAutosave();
        }

        buildInitialState(bootstrap) {
            const localDraft = this.readLocalDraft(bootstrap.survey_id);
            const source = localDraft || bootstrap;

            return {
                surveyId: source.survey_id || null,
                title: source.title || "Untitled Survey",
                description: source.description || "",
                mode: source.mode || "regular",
                visibility: source.visibility || "public",
                theme: source.theme || {
                    appearance: "light",
                    accent_color: "#2563eb",
                    font_family: "Poppins, sans-serif",
                },
                settings: {
                    collect_email: false,
                    is_anonymous: true,
                    access_password: "",
                    private_password_configured: false,
                    ...(source.settings || {}),
                },
                questions: (source.questions || []).map((question, index) =>
                    this.normalizeQuestion(question, index)
                ),
                canvasElements: (source.canvas_elements || []).map((element, index) =>
                    this.normalizeCanvasElement(element, index)
                ),
                urls: {
                    create: this.root.dataset.createUrl,
                    builder: this.root.dataset.builderUrl,
                    save: source.save_url || "",
                    preview: source.preview_url || "",
                    publish: source.publish_url || "",
                    unpublish: source.unpublish_url || "",
                },
                shareUrl: source.share_url || "",
                qrSvg: source.qr_svg || "",
                isPublished: Boolean(source.is_published),
                autosaveEnabled: source.autosave_enabled !== false,
            };
        }

        cacheElements() {
            this.saveStatus = document.getElementById("saveStatus");
            this.surveyTitleInput = document.getElementById("surveyTitleInput");
            this.surveyHeaderTitleInput = document.getElementById("surveyHeaderTitleInput");
            this.descriptionInput = document.getElementById("surveyDescriptionInput");
            this.questionList = document.getElementById("questionList");
            this.customCanvas = document.getElementById("customCanvas");
            this.canvasDropHint = document.getElementById("canvasDropHint");
            this.regularStage = document.getElementById("regularStage");
            this.customStage = document.getElementById("customStage");
            this.accentColorInput = document.getElementById("accentColorInput");
            this.fontFamilySelect = document.getElementById("fontFamilySelect");
            this.privatePasswordField = document.getElementById("privatePasswordField");
            this.privatePasswordInput = document.getElementById("privatePasswordInput");
            this.privatePasswordHelper = document.getElementById("privatePasswordHelper");
            this.collectEmailToggle = document.getElementById("collectEmailToggle");
            this.anonymousToggle = document.getElementById("anonymousToggle");
            this.shareUrlInput = document.getElementById("shareUrlInput");
            this.qrPreview = document.getElementById("qrPreview");
            this.manualSaveButton = document.getElementById("manualSaveButton");
            this.previewButton = document.getElementById("previewButton");
            this.publishButton = document.getElementById("publishButton");
            this.autosaveToggle = document.getElementById("autosaveToggle");
            this.shareBuilderButton = document.getElementById("shareBuilderButton");
            this.addQuestionButton = document.getElementById("addQuestionButton");
            this.copyShareButton = document.getElementById("copyShareButton");
            this.shareModal = document.getElementById("shareModal");
            this.closeShareModalButton = document.getElementById("closeShareModalButton");
            this.shareModalUrlInput = document.getElementById("shareModalUrlInput");
            this.copyShareModalButton = document.getElementById("copyShareModalButton");
            this.shareHelperText = document.getElementById("shareHelperText");
            this.shareModalQrPreview = document.getElementById("shareModalQrPreview");
            this.downloadQrButton = document.getElementById("downloadQrButton");
            this.shareSocialButtons = [...document.querySelectorAll("[data-share-network]")];
            this.shareCloseTargets = [...document.querySelectorAll("[data-share-close]")];
            this.modeButtons = [...document.querySelectorAll(".mode-button")];
            this.appearanceButtons = [...document.querySelectorAll(".appearance-chip")];
            this.visibilityButtons = [...document.querySelectorAll("[data-visibility]")];
            this.paletteItems = [...document.querySelectorAll(".palette-item")];
            this.toastViewport = this.ensureToastViewport();
        }

        bindEvents() {
            this.surveyTitleInput.addEventListener("input", (event) => {
                this.state.title = event.target.value;
                this.surveyHeaderTitleInput.value = event.target.value;
                this.markDirty("Title updated");
            });

            this.surveyHeaderTitleInput.addEventListener("input", (event) => {
                this.state.title = event.target.value;
                this.surveyTitleInput.value = event.target.value;
                this.markDirty("Title updated");
            });

            this.descriptionInput.addEventListener("input", (event) => {
                this.state.description = event.target.value;
                this.markDirty("Description updated");
            });

            this.accentColorInput.addEventListener("input", (event) => {
                this.state.theme.accent_color = event.target.value;
                this.markDirty("Theme updated");
            });

            this.fontFamilySelect.addEventListener("change", (event) => {
                this.state.theme.font_family = event.target.value;
                this.markDirty("Font updated");
            });

            this.privatePasswordInput.addEventListener("input", (event) => {
                this.state.settings.access_password = event.target.value;
                this.markDirty("Private access updated");
                this.renderSettings();
            });

            this.collectEmailToggle.addEventListener("change", (event) => {
                this.state.settings.collect_email = event.target.checked;
                this.markDirty("Response settings updated");
            });

            this.anonymousToggle.addEventListener("change", (event) => {
                this.state.settings.is_anonymous = event.target.checked;
                this.markDirty("Response settings updated");
            });

            this.modeButtons.forEach((button) => {
                button.addEventListener("click", () => this.setMode(button.dataset.mode));
            });

            this.appearanceButtons.forEach((button) => {
                button.addEventListener("click", () => {
                    this.state.theme.appearance = button.dataset.appearance;
                    this.markDirty("Appearance updated");
                    this.renderSettings();
                });
            });

            this.visibilityButtons.forEach((button) => {
                button.addEventListener("click", () => {
                    this.state.visibility = button.dataset.visibility;
                    this.markDirty("Access settings updated");
                    this.renderSettings();
                    this.renderShareModal();
                });
            });

            this.paletteItems.forEach((item) => {
                item.addEventListener("click", () => {
                    const questionType = item.dataset.questionType;
                    if (this.state.mode === "custom") {
                        this.addQuestion(questionType, {
                            addToCanvas: true,
                            position: this.nextCanvasPosition(),
                        });
                        return;
                    }
                    this.addQuestion(questionType);
                });

                item.addEventListener("dragstart", (event) => {
                    event.dataTransfer.setData("text/plain", item.dataset.questionType);
                });
            });

            this.addQuestionButton.addEventListener("click", () => {
                this.addQuestion("short_answer");
            });

            this.manualSaveButton.addEventListener("click", async () => {
                await this.saveSurvey({ silent: false });
            });

            this.previewButton.addEventListener("click", async () => {
                await this.openPreview();
            });

            this.publishButton.addEventListener("click", async () => {
                await this.togglePublishState();
            });

            this.autosaveToggle.addEventListener("change", (event) => {
                this.state.autosaveEnabled = event.target.checked;
                this.persistLocalDraft();
                this.setStatus(
                    event.target.checked
                        ? "AutoSave enabled"
                        : "AutoSave disabled"
                );
            });

            this.shareBuilderButton.addEventListener("click", async () => {
                await this.openShareModal();
            });

            this.copyShareButton.addEventListener("click", async () => {
                await this.copyShareLink();
            });

            this.copyShareModalButton.addEventListener("click", async () => {
                await this.copyShareLink();
            });

            this.closeShareModalButton.addEventListener("click", () => this.closeShareModal());
            this.shareCloseTargets.forEach((target) => {
                target.addEventListener("click", () => this.closeShareModal());
            });

            this.downloadQrButton.addEventListener("click", () => this.downloadQrCode());

            this.shareSocialButtons.forEach((button) => {
                button.addEventListener("click", async () => {
                    await this.handleShareAction(button.dataset.shareNetwork);
                });
            });

            window.addEventListener("keydown", (event) => {
                if (event.key === "Escape" && this.shareModal && !this.shareModal.hidden) {
                    this.closeShareModal();
                }
            });

            this.questionList.addEventListener("input", (event) => this.handleQuestionListInput(event));
            this.questionList.addEventListener("click", (event) => this.handleQuestionListClick(event));
            this.questionList.addEventListener("change", (event) => this.handleQuestionListChange(event));
            this.questionList.addEventListener("dragstart", (event) => this.handleQuestionDragStart(event));
            this.questionList.addEventListener("dragover", (event) => this.handleQuestionDragOver(event));
            this.questionList.addEventListener("drop", (event) => this.handleQuestionDrop(event));
            this.questionList.addEventListener("dragend", () => {
                this.dragQuestionId = null;
                this.renderQuestionList();
            });

            this.customCanvas.addEventListener("dragover", (event) => {
                event.preventDefault();
                this.customCanvas.classList.add("is-drop-active");
            });

            this.customCanvas.addEventListener("dragleave", () => {
                this.customCanvas.classList.remove("is-drop-active");
            });

            this.customCanvas.addEventListener("drop", (event) => {
                event.preventDefault();
                this.customCanvas.classList.remove("is-drop-active");
                const questionType = event.dataTransfer.getData("text/plain");
                if (!questionType) {
                    return;
                }

                const rect = this.customCanvas.getBoundingClientRect();
                this.addQuestion(questionType, {
                    addToCanvas: true,
                    position: {
                        x: event.clientX - rect.left - 140,
                        y: event.clientY - rect.top - 70,
                    },
                });
            });

            this.customCanvas.addEventListener("pointerdown", (event) => this.handleCanvasPointerDown(event));
            window.addEventListener("pointermove", (event) => this.handleCanvasPointerMove(event));
            window.addEventListener("pointerup", () => this.handleCanvasPointerUp());
            this.customCanvas.addEventListener("click", (event) => this.handleCanvasClick(event));
        }

        normalizeQuestion(question, index) {
            const type = question.question_type || "short_answer";
            const options = question.options && question.options.length
                ? question.options.map((option, optionIndex) => ({
                    id: option.id || null,
                    option_text: option.option_text || `Option ${optionIndex + 1}`,
                }))
                : this.requiresOptions(type)
                    ? DEFAULT_OPTIONS.map((label) => ({ option_text: label }))
                    : [];

            return {
                id: question.id || null,
                client_id: question.client_id || `question-${Date.now()}-${index}-${Math.random().toString(36).slice(2, 8)}`,
                question_text: question.question_text || "",
                question_type: type,
                is_required: Boolean(question.is_required),
                settings: {
                    placeholder: question.settings?.placeholder || "",
                    rating_max: Number(question.settings?.rating_max || 5),
                },
                options,
            };
        }

        normalizeCanvasElement(element, index) {
            return {
                id: element.id || null,
                client_id: element.client_id || `canvas-${Date.now()}-${index}`,
                question_client_id: element.question_client_id || null,
                element_type: element.element_type || "question",
                x: Number(element.x || 24),
                y: Number(element.y || 24),
                width: Number(element.width || 320),
                height: Number(element.height || 160),
                z_index: Number(element.z_index || index + 1),
                content: element.content || {},
                style: element.style || {},
            };
        }

        requiresOptions(questionType) {
            return ["multiple_choice", "checkboxes", "dropdown"].includes(questionType);
        }

        nextCanvasPosition() {
            const count = this.state.canvasElements.length;
            return {
                x: 28 + (count % 2) * 42,
                y: 28 + count * 36,
            };
        }

        addQuestion(questionType, { addToCanvas = false, position = null } = {}) {
            const question = this.normalizeQuestion(
                {
                    question_type: questionType,
                    settings: questionType === "rating" ? { rating_max: 5 } : {},
                },
                this.state.questions.length
            );
            this.state.questions.push(question);

            if (addToCanvas || this.state.mode === "custom") {
                this.state.canvasElements.push({
                    client_id: `canvas-${question.client_id}`,
                    question_client_id: question.client_id,
                    element_type: "question",
                    x: position?.x ?? this.nextCanvasPosition().x,
                    y: position?.y ?? this.nextCanvasPosition().y,
                    width: 320,
                    height: 160,
                    z_index: this.state.canvasElements.length + 1,
                    content: {
                        client_id: `canvas-${question.client_id}`,
                    },
                    style: {},
                });
            }

            this.render();
            this.markDirty(`${QUESTION_LABELS[questionType]} added`);
        }

        handleQuestionListInput(event) {
            const card = event.target.closest(".question-card");
            if (!card) {
                return;
            }

            const question = this.findQuestion(card.dataset.questionId);
            if (!question) {
                return;
            }

            if (event.target.matches("[data-field='question_text']")) {
                question.question_text = event.target.value;
            }

            if (event.target.matches("[data-field='placeholder']")) {
                question.settings.placeholder = event.target.value;
            }

            if (event.target.matches("[data-field='option_text']")) {
                const optionIndex = Number(event.target.dataset.optionIndex);
                question.options[optionIndex].option_text = event.target.value;
            }

            if (event.target.matches("[data-field='rating_max']")) {
                question.settings.rating_max = Number(event.target.value || 5);
            }

            this.markDirty("Question updated");
        }

        handleQuestionListChange(event) {
            const card = event.target.closest(".question-card");
            if (!card) {
                return;
            }

            const question = this.findQuestion(card.dataset.questionId);
            if (!question) {
                return;
            }

            if (event.target.matches("[data-field='question_type']")) {
                question.question_type = event.target.value;
                if (this.requiresOptions(question.question_type) && question.options.length === 0) {
                    question.options = DEFAULT_OPTIONS.map((label) => ({ option_text: label }));
                }
            }

            if (event.target.matches("[data-field='is_required']")) {
                question.is_required = event.target.checked;
            }

            this.render();
            this.markDirty("Question updated");
        }

        handleQuestionListClick(event) {
            const actionTarget = event.target.closest("[data-action]");
            if (!actionTarget) {
                return;
            }

            const card = event.target.closest(".question-card");
            const question = card ? this.findQuestion(card.dataset.questionId) : null;
            const action = actionTarget.dataset.action;

            if (action === "delete-question" && question) {
                this.state.questions = this.state.questions.filter(
                    (item) => item.client_id !== question.client_id
                );
                this.state.canvasElements = this.state.canvasElements.filter(
                    (item) => item.question_client_id !== question.client_id
                );
                this.render();
                this.markDirty("Question removed");
            }

            if (action === "add-option" && question) {
                question.options.push({
                    option_text: `Option ${question.options.length + 1}`,
                });
                this.renderQuestionList();
                this.markDirty("Option added");
            }

            if (action === "remove-option" && question) {
                const optionIndex = Number(actionTarget.dataset.optionIndex);
                question.options.splice(optionIndex, 1);
                this.renderQuestionList();
                this.markDirty("Option removed");
            }

            if (action === "move-question-up" && question) {
                this.moveQuestion(question.client_id, -1);
            }

            if (action === "move-question-down" && question) {
                this.moveQuestion(question.client_id, 1);
            }
        }

        moveQuestion(questionId, delta) {
            const currentIndex = this.state.questions.findIndex((question) => question.client_id === questionId);
            const targetIndex = currentIndex + delta;

            if (currentIndex < 0 || targetIndex < 0 || targetIndex >= this.state.questions.length) {
                return;
            }

            const [question] = this.state.questions.splice(currentIndex, 1);
            this.state.questions.splice(targetIndex, 0, question);
            this.renderQuestionList();
            this.markDirty("Question order updated");
        }

        handleQuestionDragStart(event) {
            const card = event.target.closest(".question-card");
            if (!card) {
                return;
            }
            this.dragQuestionId = card.dataset.questionId;
        }

        handleQuestionDragOver(event) {
            if (event.target.closest(".question-card")) {
                event.preventDefault();
            }
        }

        handleQuestionDrop(event) {
            event.preventDefault();
            const targetCard = event.target.closest(".question-card");
            if (!targetCard || !this.dragQuestionId || targetCard.dataset.questionId === this.dragQuestionId) {
                return;
            }

            const sourceIndex = this.state.questions.findIndex((item) => item.client_id === this.dragQuestionId);
            const targetIndex = this.state.questions.findIndex(
                (item) => item.client_id === targetCard.dataset.questionId
            );
            const [question] = this.state.questions.splice(sourceIndex, 1);
            this.state.questions.splice(targetIndex, 0, question);
            this.renderQuestionList();
            this.markDirty("Question order updated");
        }

        handleCanvasPointerDown(event) {
            const canvasItem = event.target.closest(".canvas-item");
            if (!canvasItem) {
                return;
            }

            const element = this.findCanvasElement(canvasItem.dataset.elementId);
            if (!element) {
                return;
            }

            const mode = event.target.classList.contains("resize-handle") ? "resize" : "drag";
            this.activeCanvasPointer = {
                elementId: element.client_id,
                mode,
                startX: event.clientX,
                startY: event.clientY,
                initialX: element.x,
                initialY: element.y,
                initialWidth: element.width,
                initialHeight: element.height,
            };

            this.bringCanvasElementToFront(element.client_id);
            this.renderCanvas();
        }

        handleCanvasPointerMove(event) {
            if (!this.activeCanvasPointer) {
                return;
            }

            const element = this.findCanvasElement(this.activeCanvasPointer.elementId);
            if (!element) {
                return;
            }

            const deltaX = event.clientX - this.activeCanvasPointer.startX;
            const deltaY = event.clientY - this.activeCanvasPointer.startY;

            if (this.activeCanvasPointer.mode === "drag") {
                element.x = Math.max(0, this.activeCanvasPointer.initialX + deltaX);
                element.y = Math.max(0, this.activeCanvasPointer.initialY + deltaY);
            } else {
                element.width = Math.max(220, this.activeCanvasPointer.initialWidth + deltaX);
                element.height = Math.max(120, this.activeCanvasPointer.initialHeight + deltaY);
            }

            this.renderCanvas();
            this.markDirty("Canvas updated");
        }

        handleCanvasPointerUp() {
            this.activeCanvasPointer = null;
        }

        handleCanvasClick(event) {
            const actionTarget = event.target.closest("[data-action]");
            if (actionTarget) {
                const canvasItem = event.target.closest(".canvas-item");
                if (!canvasItem) {
                    return;
                }
                const elementId = canvasItem.dataset.elementId;

                if (actionTarget.dataset.action === "delete-canvas-item") {
                    this.removeCanvasLinkedQuestion(elementId);
                }

                if (actionTarget.dataset.action === "layer-up") {
                    this.adjustCanvasLayer(elementId, 1);
                }

                if (actionTarget.dataset.action === "layer-down") {
                    this.adjustCanvasLayer(elementId, -1);
                }
                return;
            }

            const canvasItem = event.target.closest(".canvas-item");
            if (!canvasItem) {
                return;
            }
            this.bringCanvasElementToFront(canvasItem.dataset.elementId);
            this.renderCanvas();
        }

        removeCanvasLinkedQuestion(elementId) {
            const element = this.findCanvasElement(elementId);
            if (!element) {
                return;
            }

            this.state.canvasElements = this.state.canvasElements.filter((item) => item.client_id !== elementId);
            if (element.question_client_id) {
                this.state.questions = this.state.questions.filter(
                    (question) => question.client_id !== element.question_client_id
                );
            }
            this.render();
            this.markDirty("Canvas block removed");
        }

        adjustCanvasLayer(elementId, delta) {
            const element = this.findCanvasElement(elementId);
            if (!element) {
                return;
            }

            element.z_index = Math.max(1, element.z_index + delta);
            this.renderCanvas();
            this.markDirty("Canvas order updated");
        }

        bringCanvasElementToFront(elementId) {
            const highestLayer = Math.max(0, ...this.state.canvasElements.map((item) => item.z_index || 0));
            const element = this.findCanvasElement(elementId);
            if (element) {
                element.z_index = highestLayer + 1;
            }
        }

        setMode(mode) {
            this.state.mode = mode;
            if (mode === "custom" && this.state.questions.length && this.state.canvasElements.length === 0) {
                this.state.questions.forEach((question, index) => {
                    this.state.canvasElements.push({
                        client_id: `canvas-${question.client_id}`,
                        question_client_id: question.client_id,
                        element_type: "question",
                        x: 24 + (index % 2) * 44,
                        y: 24 + index * 46,
                        width: 320,
                        height: 160,
                        z_index: index + 1,
                        content: {
                            client_id: `canvas-${question.client_id}`,
                        },
                        style: {},
                    });
                });
            }
            this.render();
            this.markDirty(`Switched to ${mode} mode`);
        }

        render() {
            this.renderHeader();
            this.renderSettings();
            this.renderQuestionList();
            this.renderCanvas();
            this.renderModes();
            this.renderShareModal();
        }

        renderHeader() {
            this.surveyTitleInput.value = this.state.title;
            this.surveyHeaderTitleInput.value = this.state.title;
            this.descriptionInput.value = this.state.description;
            this.shareUrlInput.value = this.state.shareUrl;
            this.shareModalUrlInput.value = this.state.shareUrl;
            this.renderQrPreview(this.qrPreview);
            this.renderQrPreview(this.shareModalQrPreview);
            this.publishButton.classList.toggle("is-unpublished", this.state.isPublished);
            this.publishButton.innerHTML = this.state.isPublished
                ? '<i class="bi bi-eye-slash"></i><span>Unpublish</span>'
                : '<i class="bi bi-send-check"></i><span>Publish</span>';
            this.shareBuilderButton.innerHTML = this.state.isPublished
                ? `<i class="bi ${this.state.visibility === "private" ? "bi-shield-lock" : "bi-share"}"></i><span>Share</span>`
                : '<i class="bi bi-lock"></i><span>Share</span>';
        }

        renderSettings() {
            const isPrivateSurvey = this.state.visibility === "private";
            this.accentColorInput.value = this.state.theme.accent_color || "#2563eb";
            this.fontFamilySelect.value = this.state.theme.font_family || "Poppins, sans-serif";
            this.privatePasswordField.hidden = !isPrivateSurvey;
            this.privatePasswordField.style.display = isPrivateSurvey ? "grid" : "none";
            this.privatePasswordInput.type = "password";
            this.privatePasswordInput.value = this.state.settings.access_password || "";
            this.privatePasswordInput.required = isPrivateSurvey;
            this.collectEmailToggle.checked = Boolean(this.state.settings.collect_email);
            this.anonymousToggle.checked = Boolean(this.state.settings.is_anonymous);
            this.autosaveToggle.checked = Boolean(this.state.autosaveEnabled);

            const hasSavedPrivatePassword = Boolean(this.state.settings.private_password_configured);
            const hasDraftPassword = Boolean((this.state.settings.access_password || "").trim());
            this.privatePasswordHelper.textContent = hasDraftPassword
                ? "Private survey access is protected by this password after login."
                : hasSavedPrivatePassword
                    ? "A password is already saved for this survey. Enter a new one only if you want to change it."
                    : "Anyone opening this private survey must login first, then enter this password.";

            this.modeButtons.forEach((button) => {
                button.classList.toggle("is-active", button.dataset.mode === this.state.mode);
            });

            this.appearanceButtons.forEach((button) => {
                button.classList.toggle(
                    "is-active",
                    button.dataset.appearance === this.state.theme.appearance
                );
            });

            this.visibilityButtons.forEach((button) => {
                button.classList.toggle(
                    "is-active",
                    button.dataset.visibility === this.state.visibility
                );
            });
        }

        renderShareModal() {
            if (this.state.isPublished) {
                this.shareHelperText.textContent = this.state.visibility === "private"
                    ? "Share this private link with people who should login and enter the survey password."
                    : "Copy the public link, download the QR, or share directly to your audience.";
            } else {
                this.shareHelperText.textContent = "Publish your survey to unlock the share link, QR code, and social sharing options.";
            }
            this.downloadQrButton.disabled = !this.state.qrSvg;
            this.shareSocialButtons.forEach((button) => {
                button.disabled = !this.state.isPublished;
            });
        }

        renderQrPreview(target) {
            if (!target) {
                return;
            }

            if (!this.state.qrSvg) {
                target.innerHTML = "<span>QR code will appear here after publish.</span>";
                return;
            }

            const image = document.createElement("img");
            image.src = this.buildQrDataUrl();
            image.alt = `${(this.state.title || "Survey").trim()} QR code`;
            image.loading = "lazy";
            target.replaceChildren(image);
        }

        renderModes() {
            this.regularStage.classList.toggle("is-visible", this.state.mode === "regular");
            this.customStage.classList.toggle("is-visible", this.state.mode === "custom");
        }

        renderQuestionList() {
            if (!this.state.questions.length) {
                this.questionList.innerHTML = `
                    <div class="empty-state">
                        <h3>No questions yet</h3>
                        <p>Select a question type from the left to start building your survey.</p>
                    </div>
                `;
                return;
            }

            this.questionList.innerHTML = this.state.questions
                .map((question, index) => {
                    const optionMarkup = this.requiresOptions(question.question_type)
                        ? `
                            <div class="option-list">
                                ${question.options
                                    .map(
                                        (option, optionIndex) => `
                                            <div class="option-row">
                                                <input
                                                    type="text"
                                                    data-field="option_text"
                                                    data-option-index="${optionIndex}"
                                                    value="${this.escapeHtml(option.option_text)}"
                                                    placeholder="Option ${optionIndex + 1}"
                                                >
                                                <button type="button" class="icon-button" data-action="remove-option" data-option-index="${optionIndex}">Remove</button>
                                            </div>
                                        `
                                    )
                                    .join("")}
                                <button type="button" class="secondary-button" data-action="add-option">Add Option</button>
                            </div>
                        `
                        : "";

                    const settingsMarkup = question.question_type === "rating"
                        ? `
                            <label class="field">
                                <span>Maximum rating</span>
                                <input type="number" min="3" max="10" data-field="rating_max" value="${Number(
                                    question.settings.rating_max || 5
                                )}">
                            </label>
                        `
                        : question.question_type === "short_answer" || question.question_type === "paragraph"
                            ? `
                                <label class="field">
                                    <span>Placeholder</span>
                                    <input
                                        type="text"
                                        data-field="placeholder"
                                        value="${this.escapeHtml(question.settings.placeholder || "")}"
                                        placeholder="Optional helper text"
                                    >
                                </label>
                            `
                            : "";

                    return `
                        <article class="question-card ${this.dragQuestionId === question.client_id ? "is-dragging" : ""}" draggable="true" data-question-id="${question.client_id}">
                            <div class="question-card-header">
                                <div class="question-actions">
                                    <span class="question-index">${index + 1}</span>
                                    <div>
                                        <h4>
                                            <span class="question-type-badge">
                                                <i class="bi ${this.questionTypeIconClass(question.question_type)}"></i>
                                            </span>
                                            ${this.escapeHtml(QUESTION_LABELS[question.question_type] || "Question")}
                                        </h4>
                                        <small>${this.escapeHtml(question.client_id)}</small>
                                    </div>
                                </div>

                                <div class="question-actions">
                                    <button type="button" class="icon-button" data-action="move-question-up">Up</button>
                                    <button type="button" class="icon-button" data-action="move-question-down">Down</button>
                                    <button type="button" class="icon-button" data-action="delete-question">Delete</button>
                                </div>
                            </div>

                            <div class="question-grid">
                                <label class="field">
                                    <span>Question text</span>
                                    <input type="text" data-field="question_text" value="${this.escapeHtml(question.question_text)}" placeholder="Write your question">
                                </label>

                                <label class="field">
                                    <span>Question type</span>
                                    <select data-field="question_type">
                                        ${Object.entries(QUESTION_LABELS)
                                            .map(
                                                ([value, label]) => `
                                                    <option value="${value}" ${value === question.question_type ? "selected" : ""}>${label}</option>
                                                `
                                            )
                                            .join("")}
                                    </select>
                                </label>
                            </div>

                            ${settingsMarkup}
                            ${optionMarkup}

                            <label class="toggle-row">
                                <span>Required question</span>
                                <input type="checkbox" data-field="is_required" ${question.is_required ? "checked" : ""}>
                            </label>
                        </article>
                    `;
                })
                .join("");
        }

        renderCanvas() {
            if (!this.state.canvasElements.length) {
                this.canvasDropHint.hidden = false;
                this.customCanvas.querySelectorAll(".canvas-item").forEach((node) => node.remove());
                return;
            }

            this.canvasDropHint.hidden = true;
            const existingItems = [...this.customCanvas.querySelectorAll(".canvas-item")];
            existingItems.forEach((node) => node.remove());

            [...this.state.canvasElements]
                .sort((left, right) => left.z_index - right.z_index)
                .forEach((element) => {
                    const question = this.state.questions.find(
                        (item) => item.client_id === element.question_client_id
                    );
                    const item = document.createElement("article");
                    item.className = "canvas-item";
                    item.dataset.elementId = element.client_id;
                    item.style.left = `${element.x}px`;
                    item.style.top = `${element.y}px`;
                    item.style.width = `${element.width}px`;
                    item.style.minHeight = `${element.height}px`;
                    item.style.zIndex = String(element.z_index);
                    item.innerHTML = `
                        <div class="canvas-item-toolbar">
                            <strong class="canvas-item-title">${this.escapeHtml(
                                question?.question_text || QUESTION_LABELS[question?.question_type] || "Question block"
                            )}</strong>
                            <div class="question-actions">
                                <button type="button" class="icon-button" data-action="layer-down">Back</button>
                                <button type="button" class="icon-button" data-action="layer-up">Front</button>
                                <button type="button" class="icon-button" data-action="delete-canvas-item">Delete</button>
                            </div>
                        </div>
                        <div class="canvas-item-body">${this.describeCanvasQuestion(question)}</div>
                        <span class="resize-handle" aria-hidden="true"></span>
                    `;
                    this.customCanvas.appendChild(item);
                });
        }

        describeCanvasQuestion(question) {
            if (!question) {
                return "Drag to move this block or resize it from the corner.";
            }
            if (this.requiresOptions(question.question_type)) {
                return `${question.options.length} option(s) configured`;
            }
            if (question.question_type === "rating") {
                return `${question.settings.rating_max || 5} star rating`;
            }
            return QUESTION_LABELS[question.question_type];
        }

        questionTypeIconClass(questionType) {
            return QUESTION_ICONS[questionType] || "bi-ui-checks-grid";
        }

        findQuestion(questionId) {
            return this.state.questions.find((question) => question.client_id === questionId);
        }

        findCanvasElement(elementId) {
            return this.state.canvasElements.find((element) => element.client_id === elementId);
        }

        buildPayload() {
            return {
                title: (this.state.title || "Untitled Survey").trim(),
                description: this.state.description,
                mode: this.state.mode,
                visibility: this.state.visibility,
                theme: this.state.theme,
                settings: this.state.settings,
                questions: this.state.questions.map((question) => ({
                    client_id: question.client_id,
                    question_text: question.question_text.trim(),
                    question_type: question.question_type,
                    is_required: question.is_required,
                    settings: question.settings,
                    options: question.options
                        .filter((option) => option.option_text.trim())
                        .map((option) => ({
                            option_text: option.option_text.trim(),
                        })),
                })),
                canvas_elements: this.state.canvasElements.map((element) => ({
                    client_id: element.client_id,
                    question_client_id: element.question_client_id,
                    element_type: element.element_type,
                    x: element.x,
                    y: element.y,
                    width: element.width,
                    height: element.height,
                    z_index: element.z_index,
                    content: element.content,
                    style: element.style,
                })),
            };
        }

        validate(forPublish = false) {
            if (!this.state.title.trim()) {
                this.notify("Add a survey title before continuing.", "error");
                return false;
            }

            if (forPublish && this.state.questions.length === 0) {
                this.notify("Add at least one question before publishing.", "error");
                return false;
            }

            if (
                forPublish &&
                this.state.visibility === "private" &&
                !this.state.settings.private_password_configured &&
                !(this.state.settings.access_password || "").trim()
            ) {
                this.notify("Add a password before publishing a private survey.", "error");
                return false;
            }

            if (forPublish) {
                for (const [index, question] of this.state.questions.entries()) {
                    if (!question.question_text.trim()) {
                        this.notify(`Question ${index + 1} needs text before publishing.`, "error");
                        return false;
                    }

                    if (this.requiresOptions(question.question_type) && question.options.filter((option) => option.option_text.trim()).length < 2) {
                        this.notify(`Question ${index + 1} needs at least two options.`, "error");
                        return false;
                    }
                }
            }

            return true;
        }

        async ensureSurveyExists() {
            if (this.state.surveyId) {
                return;
            }

            const response = await this.postJson(this.state.urls.create, {
                title: this.state.title,
                description: this.state.description,
                mode: this.state.mode,
                visibility: this.state.visibility,
                theme: this.state.theme,
                settings: this.state.settings,
            });

            this.state.surveyId = response.survey_id;
            this.state.urls.save = response.save_url;
            this.state.urls.preview = response.preview_url;
            this.state.urls.publish = response.publish_url;
            this.state.urls.unpublish = response.unpublish_url || "";
            this.state.shareUrl = response.share_url || "";
            this.moveDraftStorageKey();

            if (response.builder_url) {
                history.replaceState({}, "", response.builder_url);
            }
        }

        async saveSurvey({ silent = false } = {}) {
            if (!this.validate(false) || this.isSaving) {
                return;
            }

            this.isSaving = true;
            this.setStatus("Saving draft...");

            try {
                await this.ensureSurveyExists();
                const response = await this.postJson(this.state.urls.save, this.buildPayload());
                this.ingestServerSurvey(response.survey);
                this.isDirty = false;
                this.persistLocalDraft();
                this.setStatus(silent ? "Autosaved" : response.message || "Survey saved");
                if (!silent) {
                    this.notify(response.message || "Survey saved successfully.", "success");
                }
            } catch (error) {
                this.setStatus("Save failed");
                this.notify(error.message || "Unable to save the survey right now.", "error");
            } finally {
                this.isSaving = false;
            }
        }

        async publishSurvey() {
            if (!this.validate(true) || this.isSaving) {
                return;
            }

            this.isSaving = true;
            this.setStatus("Publishing...");

            try {
                await this.ensureSurveyExists();
                const response = await this.postJson(this.state.urls.publish, this.buildPayload());
                this.ingestServerSurvey(response.survey);
                this.isDirty = false;
                this.persistLocalDraft();
                this.notify(response.message || "Survey published successfully.", "success");
                this.setStatus("Published");
            } catch (error) {
                this.setStatus("Publish failed");
                this.notify(error.message || "Unable to publish the survey.", "error");
            } finally {
                this.isSaving = false;
            }
        }

        async unpublishSurvey() {
            if (this.isSaving) {
                return;
            }

            this.isSaving = true;
            this.setStatus("Updating publish status...");

            try {
                await this.ensureSurveyExists();
                const response = await this.postJson(this.state.urls.unpublish, this.buildPayload());
                this.ingestServerSurvey(response.survey);
                this.isDirty = false;
                this.persistLocalDraft();
                this.notify(response.message || "Survey unpublished successfully.", "success");
                this.setStatus("Unpublished");
            } catch (error) {
                this.setStatus("Update failed");
                this.notify(error.message || "Unable to unpublish the survey.", "error");
            } finally {
                this.isSaving = false;
            }
        }

        async togglePublishState() {
            if (this.state.isPublished) {
                await this.unpublishSurvey();
                return;
            }
            await this.publishSurvey();
        }

        async openPreview() {
            try {
                if (this.isDirty || !this.state.surveyId) {
                    await this.saveSurvey({ silent: true });
                }

                if (!this.state.urls.preview) {
                    this.notify("Preview is not available yet.", "info");
                    return;
                }

                window.open(this.state.urls.preview, "_blank", "noopener,noreferrer");
            } catch (error) {
                this.notify(error.message || "Unable to open preview.", "error");
            }
        }

        ingestServerSurvey(survey) {
            const localDraftPassword = this.state.settings.access_password || "";
            this.state.surveyId = survey.survey_id;
            this.state.title = survey.title;
            this.state.description = survey.description;
            this.state.mode = survey.mode;
            this.state.visibility = survey.visibility || this.state.visibility;
            this.state.theme = survey.theme;
            this.state.settings = {
                ...(survey.settings || {}),
                access_password: localDraftPassword || (survey.settings?.access_password || ""),
            };
            this.state.questions = (survey.questions || []).map((question, index) =>
                this.normalizeQuestion(question, index)
            );
            this.state.canvasElements = (survey.canvas_elements || []).map((element, index) =>
                this.normalizeCanvasElement(element, index)
            );
            this.state.urls.save = survey.save_url || this.state.urls.save;
            this.state.urls.preview = survey.preview_url || this.state.urls.preview;
            this.state.urls.publish = survey.publish_url || this.state.urls.publish;
            this.state.urls.unpublish = survey.unpublish_url || this.state.urls.unpublish;
            this.state.shareUrl = survey.share_url || this.state.shareUrl;
            this.state.qrSvg = survey.qr_svg || this.state.qrSvg;
            this.state.isPublished = Boolean(survey.is_published);
            this.render();
        }

        startAutosave() {
            this.autosaveTimer = window.setInterval(() => {
                if (this.state.autosaveEnabled && this.isDirty && !this.isSaving) {
                    this.saveSurvey({ silent: true });
                }
            }, 5000);
        }

        async openShareModal() {
            if (this.isDirty && this.state.autosaveEnabled) {
                await this.saveSurvey({ silent: true });
            }

            this.shareModal.hidden = false;
            document.body.style.overflow = "hidden";
        }

        closeShareModal() {
            this.shareModal.hidden = true;
            document.body.style.overflow = "";
        }

        async copyShareLink() {
            if (!this.state.shareUrl) {
                this.notify("Publish the survey first to generate a share link.", "info");
                return;
            }

            await navigator.clipboard.writeText(this.state.shareUrl);
            this.notify("Share link copied to clipboard.", "success");
        }

        buildShareMessage() {
            const title = (this.state.title || "Survey").trim();
            return `Please respond to my survey: ${title}`;
        }

        buildShareUrl(network) {
            const link = encodeURIComponent(this.state.shareUrl);
            const message = encodeURIComponent(`${this.buildShareMessage()} ${this.state.shareUrl}`);
            const title = encodeURIComponent(this.state.title || "SurveySnap survey");

            if (network === "whatsapp") {
                return `https://wa.me/?text=${message}`;
            }
            if (network === "linkedin") {
                return `https://www.linkedin.com/sharing/share-offsite/?url=${link}`;
            }
            if (network === "facebook") {
                return `https://www.facebook.com/sharer/sharer.php?u=${link}`;
            }
            if (network === "twitter") {
                return `https://twitter.com/intent/tweet?text=${message}`;
            }
            if (network === "email") {
                return `mailto:?subject=${title}&body=${message}`;
            }
            return "";
        }

        async handleShareAction(network) {
            if (!this.state.isPublished || !this.state.shareUrl) {
                this.notify("Publish the survey before sharing it.", "info");
                return;
            }

            if (network === "native") {
                if (navigator.share) {
                    await navigator.share({
                        title: this.state.title || "SurveySnap survey",
                        text: this.buildShareMessage(),
                        url: this.state.shareUrl,
                    });
                    return;
                }
                await this.copyShareLink();
                this.notify("System share is not available in this browser. Link copied instead.", "info");
                return;
            }

            if (network === "instagram") {
                await this.copyShareLink();
                window.open("https://www.instagram.com/", "_blank", "noopener,noreferrer");
                this.notify("Link copied. Paste it into Instagram bio, story, or DM.", "success");
                return;
            }

            const shareUrl = this.buildShareUrl(network);
            if (!shareUrl) {
                this.notify("That sharing channel is not available right now.", "info");
                return;
            }

            window.open(shareUrl, "_blank", "noopener,noreferrer,width=720,height=680");
        }

        buildQrDataUrl() {
            return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(this.state.qrSvg)}`;
        }

        buildQrFilename(extension) {
            const baseName = (this.state.title || "survey")
                .trim()
                .replace(/[^a-z0-9]+/gi, "-")
                .replace(/^-+|-+$/g, "")
                .toLowerCase();
            return `${baseName || "survey"}-qr.${extension}`;
        }

        async downloadQrCode() {
            const svg = this.state.qrSvg;
            if (!svg) {
                this.notify("Publish the survey to generate a QR code first.", "info");
                return;
            }

            const image = new Image();
            image.decoding = "async";

            try {
                await new Promise((resolve, reject) => {
                    image.onload = resolve;
                    image.onerror = () => reject(new Error("Unable to render the QR code for download."));
                    image.src = this.buildQrDataUrl();
                });

                const size = Math.max(image.naturalWidth || 512, image.naturalHeight || 512, 512);
                const canvas = document.createElement("canvas");
                canvas.width = size;
                canvas.height = size;

                const context = canvas.getContext("2d");
                if (!context) {
                    throw new Error("Canvas export is not available in this browser.");
                }

                context.fillStyle = "#ffffff";
                context.fillRect(0, 0, size, size);
                context.drawImage(image, 0, 0, size, size);

                const jpegBlob = await new Promise((resolve, reject) => {
                    canvas.toBlob(
                        (blob) => {
                            if (blob) {
                                resolve(blob);
                                return;
                            }
                            reject(new Error("Unable to generate the JPEG file."));
                        },
                        "image/jpeg",
                        0.95
                    );
                });

                const objectUrl = URL.createObjectURL(jpegBlob);
                const link = document.createElement("a");
                link.href = objectUrl;
                link.download = this.buildQrFilename("jpg");
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(objectUrl);
            } catch (error) {
                this.notify(error.message || "Unable to download the QR code right now.", "error");
            }
        }

        markDirty(status) {
            this.isDirty = true;
            this.setStatus(status || "Unsaved changes");
            window.clearTimeout(this.localPersistTimer);
            this.localPersistTimer = window.setTimeout(() => this.persistLocalDraft(), 400);
        }

        persistLocalDraft() {
            const key = this.localStorageKey(this.state.surveyId);
            localStorage.setItem(
                key,
                JSON.stringify({
                    ...this.buildPayload(),
                    settings: this.state.settings,
                    survey_id: this.state.surveyId,
                    share_url: this.state.shareUrl,
                    save_url: this.state.urls.save,
                    preview_url: this.state.urls.preview,
                    publish_url: this.state.urls.publish,
                    unpublish_url: this.state.urls.unpublish,
                    qr_svg: this.state.qrSvg,
                    is_published: this.state.isPublished,
                    autosave_enabled: this.state.autosaveEnabled,
                    saved_at: new Date().toISOString(),
                })
            );
        }

        readLocalDraft(surveyId) {
            const key = this.localStorageKey(surveyId);
            const raw = localStorage.getItem(key);
            if (!raw) {
                return null;
            }

            try {
                return JSON.parse(raw);
            } catch (error) {
                localStorage.removeItem(key);
                return null;
            }
        }

        moveDraftStorageKey() {
            const unsavedKey = this.localStorageKey(null);
            const savedKey = this.localStorageKey(this.state.surveyId);
            const unsavedDraft = localStorage.getItem(unsavedKey);
            if (unsavedDraft) {
                localStorage.setItem(savedKey, unsavedDraft);
                localStorage.removeItem(unsavedKey);
            }
        }

        localStorageKey(surveyId) {
            return `surveysnap.builder.${surveyId || "new"}`;
        }

        setStatus(text) {
            this.saveStatus.textContent = text;
        }

        ensureToastViewport() {
            let viewport = document.getElementById("builderToastViewport");
            if (viewport) {
                return viewport;
            }

            viewport = document.createElement("div");
            viewport.id = "builderToastViewport";
            viewport.className = "builder-toast-viewport";
            viewport.setAttribute("aria-live", "polite");
            viewport.setAttribute("aria-atomic", "true");
            document.body.appendChild(viewport);
            return viewport;
        }

        dismissToast(toast) {
            if (!toast) {
                return;
            }

            const timerId = this.toastTimerIds.get(toast);
            if (timerId) {
                window.clearTimeout(timerId);
                this.toastTimerIds.delete(toast);
            }

            toast.classList.add("is-leaving");
            window.setTimeout(() => {
                toast.remove();
            }, 220);
        }

        notify(message, type) {
            const level = type === "error" ? "error" : type === "success" ? "success" : "info";
            const iconClass = level === "error"
                ? "bi-exclamation-octagon-fill"
                : level === "success"
                    ? "bi-check-circle-fill"
                    : "bi-info-circle-fill";
            const label = level.charAt(0).toUpperCase() + level.slice(1);

            const toast = document.createElement("section");
            toast.className = `builder-toast is-${level}`;
            toast.setAttribute("role", level === "error" ? "alert" : "status");

            toast.innerHTML = `
                <div class="builder-toast-icon" aria-hidden="true">
                    <i class="bi ${iconClass}"></i>
                </div>
                <div class="builder-toast-copy">
                    <strong>${label}</strong>
                    <p>${this.escapeHtml(message)}</p>
                </div>
                <button type="button" class="builder-toast-close" aria-label="Dismiss notification">
                    <i class="bi bi-x-lg"></i>
                </button>
            `;

            const closeButton = toast.querySelector(".builder-toast-close");
            closeButton.addEventListener("click", () => this.dismissToast(toast));

            this.toastViewport.prepend(toast);

            const timerId = window.setTimeout(() => this.dismissToast(toast), 3200);
            this.toastTimerIds.set(toast, timerId);
        }

        async postJson(url, payload) {
            const response = await fetch(url, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": this.getCsrfToken(),
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json();
            if (!response.ok || data.status === "error") {
                throw new Error(data.message || "Request failed.");
            }

            return data;
        }

        getCsrfToken() {
            const cookie = document.cookie
                .split(";")
                .map((item) => item.trim())
                .find((item) => item.startsWith("csrftoken="));
            return cookie ? cookie.split("=")[1] : "";
        }

        escapeHtml(value) {
            return String(value || "")
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#39;");
        }
    }

    const bootstrap = JSON.parse(bootstrapNode.textContent);
    new SurveyBuilderApp(root, bootstrap);
})();
