export type PortalLang = "en" | "ar";

export interface PortalDictionary {
  navAriaLabel: string;
  homeAriaLabel: string;
  profileAriaLabel: string;
  languageSwitchLabel: string;
  loadingText: string;
  loadErrorFallback: string;
  tryAgain: string;
  returnToSignIn: string;
  enrolmentActiveLabel: string;
  syntheticAccountBadge: string;
  permissionFirstTitle: string;
  permissionFirstBody: string;
  reviewPrivacyChoices: string;
  momentTag: string;
  viewTodaysCheckin: string;
  exploreActivities: string;
  letsCheckIn: string;
  screeningTitle: string;
  screeningSubtitle: string;
  awaitingResult: string;
  urgentTitle: string;
  urgentBody: string;
  viewCareInfo: string;
  todayTitle: string;
  checkinDoneToday: string;
  wearableTaskTitle: string;
  wearableTaskHasData: string;
  wearableTaskNoData: string;
  careConnectedTitle: string;
  defaultCareTeam: string;
  defaultCareRole: string;
  openCarePlan: string;
  healthSignalsTitle: string;
  healthSignalsSubtitle: string;
  healthSignalSelectAria: string;
  noReadingsYet: string;
  observationsEmpty: string;
  missingReadingsNote: string;
  latestReadingPrefix: string;
  noticeAcknowledge: string;
  noticeAcknowledged: string;
  noticeAckSuccess: string;
  memoryTitle: string;
  memoryDesc: string;
  memoryReady: string;
  memoryWatch: string;
  memoryRepeatPrefix: string;
  memoryRepeatOfTotal: string;
  memorySaving: string;
  memorySaved: string;
  memoryFailed: string;
  memoryTilePrefix: string;
  memoryStart: string;
  memoryAnother: string;
  moodLabel: string;
  readinessLabel: string;
  moodLow: string;
  moodHigh: string;
  stressLabel: string;
  stressLow: string;
  stressHigh: string;
  cravingLabel: string;
  cravingLow: string;
  cravingHigh: string;
  shiftLabel: string;
  shiftPlaceholder: string;
  worksiteLabel: string;
  worksitePlaceholder: string;
  reflectionPlaceholder: string;
  urgentCheckboxLabel: string;
  emergencyDisclaimer: string;
  checkinReceived: string;
  checkinSending: string;
  checkinSend: string;
  checkinSuccessUrgent: string;
  checkinSuccessRoutine: string;
  startAnotherCheckin: string;
  recentCheckinsTitle: string;
  recentCheckinsEmpty: string;
  moodShort: string;
  stressShort: string;
  wearableTitle: string;
  wearableDesc: string;
  wearableProviderNote: string;
  wearableAwaitingConfig: string;
  wearableUnavailable: string;
  importTitle: string;
  importDesc: string;
  chooseCsv: string;
  csvLimitNote: string;
  downloadExampleCsv: string;
  syntheticExampleNote: string;
  manageWearableConsent: string;
  wearableImportSuccess: string;
  csvSizeError: string;
  csvHeaderError: string;
  csvRowError: string;
  careHeroTitle: string;
  careHeroPrefix: string;
  careHeroSuffix: string;
  assignedFacilityFallback: string;
  outcomePrefix: string;
  careEmptyText: string;
  profileEnrolmentNote: string;
  privacyTitle: string;
  privacySubtitle: string;
  consentSavedSuccess: string;
  signOut: string;
  footerPoweredBy: string;
  metrics: {
    sleep_hours: string;
    hrv_rmssd: string;
    resting_hr: string;
    steps: string;
    hba1c: string;
    bp_systolic: string;
    bp_diastolic: string;
    resting_hr_short: string;
  };
  nav: Record<"home" | "checkin" | "devices" | "care" | "profile", string>;
  programmes: Record<
    "core" | "loop" | "neuro" | "worksafe",
    {
      name: string;
      title: string;
      description: string;
      activity: string;
      prompt: string;
      subtitle: string;
    }
  >;
  consents: Record<
    | "data_processing"
    | "wearable_ingestion"
    | "llm_synthesis"
    | "family_notification"
    | "hie_sharing"
    | "optional_channels",
    { title: string; detail: string }
  >;
  formatSpaceTitle: (programmeName: string) => string;
  formatHello: (name: string) => string;
}

const EN: PortalDictionary = {
  navAriaLabel: "Patient navigation",
  homeAriaLabel: "Recova patient home",
  profileAriaLabel: "Your profile and privacy",
  languageSwitchLabel: "العربية",
  loadingText: "Getting your care space ready…",
  loadErrorFallback: "Your care information could not be loaded.",
  tryAgain: "Try again",
  returnToSignIn: "Return to sign in",
  enrolmentActiveLabel: "Active programme enrolment:",
  syntheticAccountBadge: "Synthetic test account",
  permissionFirstTitle: "Your permission comes first",
  permissionFirstBody:
    "Review how your care information is used before sending an activity or importing wearable data.",
  reviewPrivacyChoices: "Review privacy choices",
  momentTag: "A moment for your wellbeing",
  viewTodaysCheckin: "View today's check-in",
  exploreActivities: "Explore your activities",
  letsCheckIn: "Let's check in",
  screeningTitle: "Your screening snapshot",
  screeningSubtitle:
    "Results recorded by your facility. Your care team will explain your follow-up.",
  awaitingResult: "Awaiting result",
  urgentTitle: "Urgent support requested",
  urgentBody:
    "An urgent-support request is in your check-in history. Contact your facility directly for support. Use your local emergency service in immediate danger.",
  viewCareInfo: "View my care information",
  todayTitle: "Today, at your pace",
  checkinDoneToday: "Check-in received today",
  wearableTaskTitle: "Your wearable signals",
  wearableTaskHasData: "View readings and import updates",
  wearableTaskNoData: "Bring your readings into your care",
  careConnectedTitle: "Your care, connected",
  defaultCareTeam: "Your facility care team",
  defaultCareRole: "Check your next care actions",
  openCarePlan: "Open my care plan",
  healthSignalsTitle: "Your health signals",
  healthSignalsSubtitle: "Your recent observations, at a glance",
  healthSignalSelectAria: "Health signal",
  noReadingsYet: "No readings yet",
  observationsEmpty: "Your observations will appear here after your first import.",
  missingReadingsNote:
    "Missing readings stay visible so your care team can interpret the available information.",
  latestReadingPrefix: "Latest reading",
  noticeAcknowledge: "I have read this",
  noticeAcknowledged: "Acknowledged",
  noticeAckSuccess: "Notice acknowledged.",
  memoryTitle: "Memory moments",
  memoryDesc:
    "Watch three numbered tiles light up, then tap them in the same order. This is a practice activity. Your team can use the saved session when reviewing your progress.",
  memoryReady: "Ready when you are",
  memoryWatch: "Watch the sequence",
  memoryRepeatPrefix: "Your turn ·",
  memoryRepeatOfTotal: "of 3",
  memorySaving: "Saving your activity…",
  memorySaved: "Activity saved for your care team.",
  memoryFailed: "Could not save. Please try the activity again.",
  memoryTilePrefix: "Tile",
  memoryStart: "Start activity",
  memoryAnother: "Try another activity",
  moodLabel: "How are you feeling today?",
  readinessLabel: "How ready do you feel for your shift?",
  moodLow: "Low",
  moodHigh: "Very well",
  stressLabel: "How much stress are you feeling?",
  stressLow: "Very little",
  stressHigh: "A lot",
  cravingLabel: "How strong are your cravings?",
  cravingLow: "None",
  cravingHigh: "Strong",
  shiftLabel: "Shift (Optional)",
  shiftPlaceholder: "e.g. Morning Shift A",
  worksiteLabel: "Worksite (Optional)",
  worksitePlaceholder: "e.g. Sector 4 Outdoor",
  reflectionPlaceholder: "Share what feels important to you…",
  urgentCheckboxLabel: "I need urgent support from my care team.",
  emergencyDisclaimer:
    "For immediate danger, use your local emergency service. Check-ins may take time to be reviewed.",
  checkinReceived: "Check-in received",
  checkinSending: "Sending…",
  checkinSend: "Send to my care team",
  checkinSuccessUrgent:
    "Your urgent support request has been recorded. Contact your facility directly for immediate support.",
  checkinSuccessRoutine: "Your check-in has been received by your care team.",
  startAnotherCheckin: "Start another check-in",
  recentCheckinsTitle: "Recent check-ins",
  recentCheckinsEmpty: "Your first check-in will appear here.",
  moodShort: "Mood",
  stressShort: "Stress",
  wearableTitle: "Bring your wearable into your care",
  wearableDesc:
    "Sleep, heart rate, heart rate variability and activity can help your care team understand changes over time.",
  wearableProviderNote:
    "Direct device connections need your facility’s configured provider integration. You can import an exported CSV below today.",
  wearableAwaitingConfig: "Provider connection awaiting configuration",
  wearableUnavailable: "Unavailable",
  importTitle: "Import your readings",
  importDesc:
    "Export your readings into the supported CSV format. Each reading is validated before saving.",
  chooseCsv: "Choose a wearable CSV",
  csvLimitNote: "Up to 500 readings · maximum 1 MB",
  downloadExampleCsv: "Download example CSV",
  syntheticExampleNote:
    "The example contains synthetic values. Use your own exported measurements for an actual import.",
  manageWearableConsent: "Manage wearable permission",
  wearableImportSuccess:
    "Your wearable readings were imported. You can now see them in your health signals.",
  csvSizeError: "Choose a file smaller than 1 MB.",
  csvHeaderError:
    "Use the CSV header metric,value,unit,at. Download the example below.",
  csvRowError: "Every row needs metric, numeric value, unit and timestamp.",
  careHeroTitle: "We are on your side",
  careHeroPrefix: "Your care is provided by",
  careHeroSuffix: "This space keeps your next steps together.",
  assignedFacilityFallback: "Assigned facility",
  outcomePrefix: "Outcome:",
  careEmptyText: "Your team will share your next care steps here.",
  profileEnrolmentNote:
    "Your facility enrolment determines the care activities you see. Contact your facility if your enrolment needs updating.",
  privacyTitle: "Your information, your choices",
  privacySubtitle:
    "Your decisions are recorded and checked when information is processed.",
  consentSavedSuccess: "Your privacy choice has been saved.",
  signOut: "Sign out",
  footerPoweredBy: "Your care space, powered by Recova",
  metrics: {
    sleep_hours: "Sleep",
    hrv_rmssd: "Heart rate variability",
    resting_hr: "Resting heart rate",
    steps: "Steps",
    hba1c: "HbA1c",
    bp_systolic: "Systolic BP",
    bp_diastolic: "Diastolic BP",
    resting_hr_short: "Resting HR",
  },
  nav: {
    home: "Home",
    checkin: "Check in",
    devices: "Devices",
    care: "My care",
    profile: "You",
  },
  programmes: {
    core: {
      name: "Recovery",
      title: "One day at a time.",
      description:
        "Make space for how you feel. Your care team is here for your recovery.",
      activity: "Your daily reflection",
      prompt: "What has helped your recovery today?",
      subtitle: "A little reflection goes a long way.",
    },
    loop: {
      name: "Health Loop",
      title: "Your next step to better health.",
      description:
        "Keep your screening and follow-up care together, wherever life takes you.",
      activity: "Your wellbeing check",
      prompt: "Anything you would like your care team to know?",
      subtitle: "Keep your care team up to date.",
    },
    neuro: {
      name: "Brain Health",
      title: "A little practice. A clearer picture.",
      description:
        "Build a picture of your wellbeing over time with gentle cognitive activities.",
      activity: "Your memory activity",
      prompt: "How did you feel during today's activity?",
      subtitle: "Take your time and find a quiet place.",
    },
    worksafe: {
      name: "WorkSafe",
      title: "Start your shift with you.",
      description:
        "A quick check on your energy, rest and wellbeing before the working day.",
      activity: "Your shift readiness",
      prompt: "Tell your occupational-health team about your shift or any concerns.",
      subtitle: "A quick pause before your shift.",
    },
  },
  consents: {
    data_processing: {
      title: "Care-data processing",
      detail:
        "Allow your observations and check-ins to support your care programme.",
    },
    wearable_ingestion: {
      title: "Wearable readings",
      detail:
        "Allow wearable file imports to be stored with your care record.",
    },
    llm_synthesis: {
      title: "AI-assisted clinical summaries",
      detail:
        "Allow eligible information to be sent to a configured summary provider for clinician review.",
    },
    family_notification: {
      title: "Family notifications",
      detail: "Allow the facility's approved family-contact workflow.",
    },
    hie_sharing: {
      title: "Health information exchange",
      detail: "Allow approved health-information sharing integrations.",
    },
    optional_channels: {
      title: "Optional external channels",
      detail:
        "Allow optional SMS or email updates when configured by your facility.",
    },
  },
  formatSpaceTitle: (programmeName: string) => `Your ${programmeName} space`,
  formatHello: (name: string) => `Hello, ${name}`,
};

const AR: PortalDictionary = {
  navAriaLabel: "تنقل المريض",
  homeAriaLabel: "الصفحة الرئيسية لبوابة ريكوفا للمريض",
  profileAriaLabel: "ملفك الشخصي والخصوصية",
  languageSwitchLabel: "English",
  loadingText: "جارٍ تجهيز مساحة رعايتك…",
  loadErrorFallback: "تعذّر تحميل بيانات رعايتك.",
  tryAgain: "حاول مرة أخرى",
  returnToSignIn: "العودة إلى تسجيل الدخول",
  enrolmentActiveLabel: "التسجيل النشط في البرنامج:",
  syntheticAccountBadge: "حساب اختباري اصطناعي",
  permissionFirstTitle: "موافقتك أولاً",
  permissionFirstBody:
    "راجع كيفية استخدام معلومات رعايتك قبل إرسال أي نشاط أو استيراد بيانات الأجهزة القابلة للارتداء.",
  reviewPrivacyChoices: "مراجعة خيارات الخصوصية",
  momentTag: "لحظة للاطمئنان على صحتك",
  viewTodaysCheckin: "عرض تسجيل اليوم",
  exploreActivities: "استكشف أنشطتك",
  letsCheckIn: "ابدأ التسجيل اليومي",
  screeningTitle: "ملخص الفحص الصحي",
  screeningSubtitle:
    "النتائج المسجلة في منشأتك. سيشرح لك فريق الرعاية خطوات المتابعة.",
  awaitingResult: "بانتظار النتيجة",
  urgentTitle: "تم طلب دعم عاجل",
  urgentBody:
    "يوجد طلب دعم عاجل في سجل متابعتك. تواصل مع منشأتك مباشرة للحصول على الدعم، واتصل بخدمات الطوارئ المحلية عند وجود خطر فوري.",
  viewCareInfo: "عرض معلومات رعايتي",
  todayTitle: "اليوم، بالوتيرة التي تناسبك",
  checkinDoneToday: "تم استلام تسجيل اليوم",
  wearableTaskTitle: "مؤشرات جهازك القابل للارتداء",
  wearableTaskHasData: "عرض القراءات واستيراد التحديثات",
  wearableTaskNoData: "أضف قراءاتك إلى ملف رعايتك",
  careConnectedTitle: "رعايتك متصلة بك",
  defaultCareTeam: "فريق الرعاية في منشأتك",
  defaultCareRole: "اطّلع على خطوات الرعاية القادمة",
  openCarePlan: "فتح خطة رعايتي",
  healthSignalsTitle: "مؤشراتك الصحية",
  healthSignalsSubtitle: "أحدث قراءاتك الصحية في لمحة سريعة",
  healthSignalSelectAria: "المؤشر الصحي",
  noReadingsYet: "لا توجد قراءات بعد",
  observationsEmpty: "ستظهر قراءاتك هنا بعد أول عملية استيراد.",
  missingReadingsNote:
    "تبقى القراءات المفقودة ظاهرة ليتمكن فريق الرعاية من تفسير البيانات المتاحة بدقة.",
  latestReadingPrefix: "آخر قراءة",
  noticeAcknowledge: "لقد قرأت هذا التنبيه",
  noticeAcknowledged: "تم تأكيد القراءة",
  noticeAckSuccess: "تم تسجيل اطلاعك على التنبيه.",
  memoryTitle: "تمارين الذاكرة",
  memoryDesc:
    "راقب إضاءة ثلاثة مربعات مرقمة، ثم اضغط عليها بنفس الترتيب. هذا نشاط تدريبي ويمكن لفريق الرعاية مراجعة الجلسة المحفوظة لمتابعة تقدمك.",
  memoryReady: "جاهز عندما تكون مستعداً",
  memoryWatch: "راقب التسلسل",
  memoryRepeatPrefix: "دورك الآن ·",
  memoryRepeatOfTotal: "من 3",
  memorySaving: "جارٍ حفظ نشاطك…",
  memorySaved: "تم حفظ النشاط لفريق الرعاية.",
  memoryFailed: "تعذّر الحفظ. يرجى إعادة المحاولة.",
  memoryTilePrefix: "مربع",
  memoryStart: "بدء النشاط",
  memoryAnother: "تجربة نشاط آخر",
  moodLabel: "كيف تشعر اليوم؟",
  readinessLabel: "ما مدى جاهزيتك لبدء نوبة العمل؟",
  moodLow: "منخفض",
  moodHigh: "ممتاز جداً",
  stressLabel: "ما مستوى التوتر الذي تشعر به؟",
  stressLow: "قليل جداً",
  stressHigh: "مرتفع جداً",
  cravingLabel: "ما مدى شدة الرغبة الملحة لديك؟",
  cravingLow: "لا توجد",
  cravingHigh: "شديدة",
  shiftLabel: "نوبة العمل (اختياري)",
  shiftPlaceholder: "مثال: النوبة الصباحية أ",
  worksiteLabel: "موقع العمل (اختياري)",
  worksitePlaceholder: "مثال: القطاع 4 الخارجي",
  reflectionPlaceholder: "شارك ما تود إخبار فريق الرعاية به…",
  urgentCheckboxLabel: "أحتاج إلى دعم عاجل من فريق الرعاية.",
  emergencyDisclaimer:
    "في حالات الخطر الفوري، اتصل بخدمات الطوارئ المحلية. قد تستغرق مراجعة التسجيلات اليومية بعض الوقت.",
  checkinReceived: "تم استلام التسجيل",
  checkinSending: "جارٍ الإرسال…",
  checkinSend: "إرسال إلى فريق الرعاية",
  checkinSuccessUrgent:
    "تم تسجيل طلب الدعم العاجل. تواصل مع منشأتك مباشرة للحصول على مساعدة فورية.",
  checkinSuccessRoutine: "تم استلام تسجيلك اليومي من قبل فريق الرعاية.",
  startAnotherCheckin: "بدء تسجيل يومي جديد",
  recentCheckinsTitle: "التسجيلات الأخيرة",
  recentCheckinsEmpty: "سيظهر أول تسجيل يومي لك هنا.",
  moodShort: "المزاج",
  stressShort: "التوتر",
  wearableTitle: "اربط جهازك القابل للارتداء برعايتك",
  wearableDesc:
    "تساعد قراءات النوم ومعدل نبض القلب وتقلّبه والنشاط البدني فريق الرعاية على متابعة التغيرات بمرور الوقت.",
  wearableProviderNote:
    "يتطلب الربط المباشر تفعيل مزوّد الخدمة لدى منشأتك. يمكنك استيراد ملف CSV المصدّر أدناه اليوم.",
  wearableAwaitingConfig: "الربط مع المزوّد بانتظار الإعداد",
  wearableUnavailable: "غير متاح",
  importTitle: "استيراد قراءاتك",
  importDesc:
    "صدّر قراءاتك بصيغة CSV المدعومة. يتم التحقق من كل قراءة قبل حفظها.",
  chooseCsv: "اختر ملف CSV للجهاز",
  csvLimitNote: "حتى 500 قراءة · الحد الأقصى 1 ميغابايت",
  downloadExampleCsv: "تنزيل مثال ملف CSV",
  syntheticExampleNote:
    "يحتوي المثال على قيم تجريبية. استخدم قياساتك المصدّرة الفعلية عند الاستيراد الحقيقي.",
  manageWearableConsent: "إدارة إذن الأجهزة القابلة للارتداء",
  wearableImportSuccess:
    "تم استيراد قراءات جهازك بنجاح ويمكنك رؤيتها الآن في مؤشراتك الصحية.",
  csvSizeError: "اختر ملفاً أصغر من 1 ميغابايت.",
  csvHeaderError:
    "استخدم ترويسة الأعمدة metric,value,unit,at. يمكنك تنزيل المثال أدناه.",
  csvRowError: "يجب أن يحتوي كل صف على اسم المؤشر والقيمة الرقمية والوحدة والوقت.",
  careHeroTitle: "نحن معك في كل خطوة",
  careHeroPrefix: "تُقدَّم رعايتك من خلال",
  careHeroSuffix: "تحفظ هذه المساحة خطوات رعايتك ومواعيدك معاً.",
  assignedFacilityFallback: "المنشأة المعنية",
  outcomePrefix: "النتيجة:",
  careEmptyText: "سيشارك فريق الرعاية خطوات المتابعة القادمة هنا.",
  profileEnrolmentNote:
    "يحدد تسجيلك في المنشأة الأنشطة المتاحة لك. تواصل مع منشأتك إذا احتاج تسجيلك إلى تحديث.",
  privacyTitle: "معلوماتك، واختياراتك",
  privacySubtitle:
    "يتم تسجيل اختياراتك والتحقق منها عند معالجة أي بيانات.",
  consentSavedSuccess: "تم حفظ تفضيلات الخصوصية الخاصة بك.",
  signOut: "تسجيل الخروج",
  footerPoweredBy: "مساحة رعايتك، بدعم من منصة ريكوفا",
  metrics: {
    sleep_hours: "النوم",
    hrv_rmssd: "تقلّب معدل نبض القلب",
    resting_hr: "معدل النبض أثناء الراحة",
    steps: "الخطوات",
    hba1c: "السكر التراكمي HbA1c",
    bp_systolic: "الضغط الانقباضي",
    bp_diastolic: "الضغط الانبساطي",
    resting_hr_short: "النبض بالراحة",
  },
  nav: {
    home: "الرئيسية",
    checkin: "التسجيل اليومي",
    devices: "الأجهزة",
    care: "رعايتي",
    profile: "حسابي",
  },
  programmes: {
    core: {
      name: "التعافي",
      title: "خطوة بخطوة، يوماً بيوم.",
      description:
        "امنح نفسك مساحة للتعبير عما تشعر به. فريق الرعاية معك في رحلة تعافيك.",
      activity: "تأملك اليومي",
      prompt: "ما الذي ساعدك في تعافيك اليوم؟",
      subtitle: "قليل من التأمل يصنع فرقاً كبيراً.",
    },
    loop: {
      name: "المتابعة الصحية",
      title: "خطوتك القادمة نحو صحة أفضل.",
      description:
        "احتفظ بنتائج الفحص ومواعيد المتابعة في مكان واحد أينما كنت.",
      activity: "اطمئنانك الصحي",
      prompt: "هل هناك ما تود إبلاغ فريق الرعاية به؟",
      subtitle: "أبقِ فريق الرعاية على اطلاع دائم.",
    },
    neuro: {
      name: "صحة الدماغ",
      title: "تدريب بسيط. صورة أوضح.",
      description:
        "كوّن صورة متكاملة عن عافيتك المعرفية بمرور الوقت عبر أنشطة ذهنية لطيفة.",
      activity: "نشاط الذاكرة",
      prompt: "كيف شعرت أثناء نشاط اليوم؟",
      subtitle: "خذ وقتك واختر مكاناً هادئاً.",
    },
    worksafe: {
      name: "السلامة المهنية",
      title: "ابدأ نوبتك بالاطمئنان على نفسك.",
      description:
        "فحص سريع لطاقتك وراحتك وجاهزيتك قبل بدء يوم العمل.",
      activity: "جاهزية نوبة العمل",
      prompt: "أخبر فريق الصحة المهنية عن نوبتك أو أي ملاحظات صحية.",
      subtitle: "وقفة سريعة قبل بدء النوبة.",
    },
  },
  consents: {
    data_processing: {
      title: "معالجة بيانات الرعاية",
      detail: "السماح باستخدام قراءاتك وتسجيلاتك اليومية لدعم برنامج رعايتك.",
    },
    wearable_ingestion: {
      title: "قراءات الأجهزة القابلة للارتداء",
      detail: "السماح بحفظ ملفات القراءات المستوردة ضمن سجل رعايتك.",
    },
    llm_synthesis: {
      title: "الملخصات السريرية المدعومة بالذكاء الاصطناعي",
      detail:
        "السماح بإرسال المعلومات المؤهلة إلى مزوّد التلخيص المعتمد لمراجعة الطبيب.",
    },
    family_notification: {
      title: "إشعارات العائلة",
      detail: "السماح بسير عمل التواصل المعتمد مع جهة الاتصال العائلية.",
    },
    hie_sharing: {
      title: "تبادل المعلومات الصحية",
      detail: "السماح بتكاملات تبادل المعلومات الصحية المعتمدة.",
    },
    optional_channels: {
      title: "القنوات الخارجية الاختيارية",
      detail:
        "السماح بإرسال تحديثات اختيارية عبر الرسائل النصية أو البريد الإلكتروني عند تفعيلها في المنشأة.",
    },
  },
  formatSpaceTitle: (programmeName: string) => `مساحة ${programmeName}`,
  formatHello: (name: string) => `مرحباً، ${name}`,
};

export function getPortalDictionary(lang: PortalLang): PortalDictionary {
  return lang === "ar" ? AR : EN;
}
