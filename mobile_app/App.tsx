import { StatusBar } from "expo-status-bar";
import { Ionicons } from "@expo/vector-icons";
import React, { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import { DEFAULT_API_BASE_URL, fetchAdvice, sendWhatsApp } from "./src/api";
import { Advice, AdviceResponse } from "./src/types";

const CROPS = ["şaftalı/gilas", "şaftalı", "gilas"];

function formatWindowDate(value: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.replace("T", " ");

  return new Intl.DateTimeFormat("az-Latn-AZ", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function scoreTone(score?: number) {
  if (!score) return styles.scoreMuted;
  if (score >= 80) return styles.scoreGood;
  if (score >= 60) return styles.scoreCareful;
  return styles.scoreBad;
}

function ActionButton({
  label,
  icon,
  onPress,
  variant = "primary",
  disabled = false
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
}) {
  const buttonStyle = [
    styles.button,
    variant === "secondary" && styles.buttonSecondary,
    variant === "danger" && styles.buttonDanger,
    disabled && styles.buttonDisabled
  ];
  const textStyle = [
    styles.buttonText,
    variant === "secondary" && styles.buttonSecondaryText
  ];

  return (
    <Pressable style={buttonStyle} onPress={onPress} disabled={disabled}>
      <Ionicons
        name={icon}
        size={19}
        color={variant === "secondary" ? "#17433a" : "#ffffff"}
      />
      <Text style={textStyle}>{label}</Text>
    </Pressable>
  );
}

function MetaRow({ label, value }: { label: string; value: string | number }) {
  return (
    <View style={styles.metaRow}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue}>{value}</Text>
    </View>
  );
}

function AdviceCard({ advice }: { advice: Advice }) {
  const best = advice.best_window;

  return (
    <View style={styles.section}>
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Ən uyğun seçim</Text>
        <View style={[styles.scorePill, scoreTone(best?.score)]}>
          <Text style={styles.scoreText}>{best?.score || 0}/100</Text>
        </View>
      </View>

      {best?.available ? (
        <>
          <Text style={styles.windowTime}>
            {formatWindowDate(best.start)} - {formatWindowDate(best.end)}
          </Text>
          <Text style={styles.cardTitle}>{best.title}</Text>
          <Text style={styles.bodyText}>{best.reason}</Text>

          {best.cautions?.length > 0 && (
            <View style={styles.noteBlock}>
              {best.cautions.map((item, index) => (
                <Text key={`${item}-${index}`} style={styles.noteText}>
                  {index + 1}. {item}
                </Text>
              ))}
            </View>
          )}
        </>
      ) : (
        <Text style={styles.bodyText}>{advice.farmer_summary}</Text>
      )}
    </View>
  );
}

function Alternatives({ advice }: { advice: Advice }) {
  if (!advice.alternatives?.length) return null;

  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>Alternativ pəncərələr</Text>
      {advice.alternatives.map((item) => (
        <View key={`${item.rank}-${item.start}`} style={styles.altCard}>
          <View style={styles.altTop}>
            <Text style={styles.altRank}>{item.rank}-ci seçim</Text>
            <View style={[styles.smallScore, scoreTone(item.score)]}>
              <Text style={styles.smallScoreText}>{item.score}</Text>
            </View>
          </View>
          <Text style={styles.altTime}>
            {formatWindowDate(item.start)} - {formatWindowDate(item.end)}
          </Text>
          <Text style={styles.altReason}>{item.reason}</Text>
        </View>
      ))}
    </View>
  );
}

export default function App() {
  const [apiBaseUrl, setApiBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [showSettings, setShowSettings] = useState(false);
  const [activeSubstance, setActiveSubstance] = useState("gübrə 20-20-20");
  const [crop, setCrop] = useState(CROPS[0]);
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<AdviceResponse | null>(null);
  const [error, setError] = useState("");

  const advice = useMemo(() => {
    return (result?.advice || result?.fallback || null) as Advice | null;
  }, [result]);

  async function handleAnalyze() {
    const substance = activeSubstance.trim();
    if (!substance) {
      Alert.alert("Aktiv maddə lazımdır", "Dərmandakı aktiv maddəni və ya məhsul adını yaz.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const response = await fetchAdvice(apiBaseUrl.trim(), substance, crop);
      setResult(response);
      if (!response.ok && response.error) {
        setError(response.error);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analiz alınmadı.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSendWhatsApp(useCustomPhone: boolean) {
    if (!advice?.whatsapp_summary) {
      Alert.alert("Mesaj yoxdur", "Əvvəl AI analiz et.");
      return;
    }

    const targetPhone = useCustomPhone ? phone.trim() : "";
    if (useCustomPhone && !targetPhone) {
      Alert.alert("Nömrə lazımdır", "Başqa nömrəyə göndərmək üçün nömrəni yaz.");
      return;
    }

    setSending(true);
    try {
      const response = await sendWhatsApp(apiBaseUrl.trim(), advice.whatsapp_summary, targetPhone);
      if (response.sent) {
        Alert.alert("Göndərildi", "WhatsApp mesajı göndərildi.");
      } else {
        Alert.alert("Göndərilmədi", "Server mesajı göndərə bilmədi.");
      }
    } catch (err) {
      Alert.alert("Xəta", err instanceof Error ? err.message : "WhatsApp göndərilmədi.");
    } finally {
      setSending(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <View>
              <Text style={styles.eyebrow}>Xaçmaz</Text>
              <Text style={styles.title}>Çiləmə məsləhətçisi</Text>
            </View>
            <Pressable style={styles.settingsButton} onPress={() => setShowSettings(!showSettings)}>
              <Ionicons name="settings-outline" size={22} color="#17433a" />
            </Pressable>
          </View>

          {showSettings && (
            <View style={styles.settingsBox}>
              <Text style={styles.label}>Server ünvanı</Text>
              <TextInput
                value={apiBaseUrl}
                onChangeText={setApiBaseUrl}
                autoCapitalize="none"
                autoCorrect={false}
                style={styles.input}
                placeholder="https://xacmaz-weather-api.onrender.com"
              />
              <Text style={styles.helperText}>
                Normal istifadə üçün bu ünvan cloud serverin ünvanı olmalıdır.
              </Text>
            </View>
          )}

          <View style={styles.form}>
            <Text style={styles.label}>Bitki</Text>
            <View style={styles.segment}>
              {CROPS.map((item) => (
                <Pressable
                  key={item}
                  style={[styles.segmentItem, crop === item && styles.segmentItemActive]}
                  onPress={() => setCrop(item)}
                >
                  <Text style={[styles.segmentText, crop === item && styles.segmentTextActive]}>
                    {item}
                  </Text>
                </Pressable>
              ))}
            </View>

            <Text style={styles.label}>Aktiv maddə və ya məhsul</Text>
            <TextInput
              value={activeSubstance}
              onChangeText={setActiveSubstance}
              style={styles.input}
              placeholder="məsələn: captan, mis, gübrə 20-20-20"
            />

            <ActionButton
              label={loading ? "Analiz hazırlanır" : "AI analiz et"}
              icon="sparkles-outline"
              onPress={handleAnalyze}
              disabled={loading}
            />
          </View>

          {loading && (
            <View style={styles.loadingBox}>
              <ActivityIndicator color="#23685b" />
              <Text style={styles.loadingText}>Mənbələr yığılır və AI analiz edir...</Text>
            </View>
          )}

          {!!error && (
            <View style={styles.errorBox}>
              <Text style={styles.errorTitle}>Diqqət</Text>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}

          {advice && (
            <>
              <View style={styles.summary}>
                <Text style={styles.summaryTitle}>{advice.decision}</Text>
                <Text style={styles.summaryText}>{advice.farmer_summary}</Text>
              </View>

              <AdviceCard advice={advice} />

              {!!advice.detailed_report && (
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Ətraflı izah</Text>
                  <Text style={styles.bodyText}>{advice.detailed_report}</Text>
                </View>
              )}

              <Alternatives advice={advice} />

              {!!advice.warnings?.length && (
                <View style={styles.section}>
                  <Text style={styles.sectionTitle}>Xəbərdarlıqlar</Text>
                  {advice.warnings.map((item, index) => (
                    <Text key={`${item}-${index}`} style={styles.noteText}>
                      {index + 1}. {item}
                    </Text>
                  ))}
                </View>
              )}

              <View style={styles.section}>
                <Text style={styles.sectionTitle}>WhatsApp mesajı</Text>
                <Text style={styles.whatsappText}>{advice.whatsapp_summary}</Text>
                <View style={styles.buttonStack}>
                  <ActionButton
                    label={sending ? "Göndərilir" : "Mənə göndər"}
                    icon="logo-whatsapp"
                    onPress={() => handleSendWhatsApp(false)}
                    disabled={sending}
                  />
                  <TextInput
                    value={phone}
                    onChangeText={setPhone}
                    keyboardType="phone-pad"
                    style={styles.input}
                    placeholder="Başqa nömrə: 994XXXXXXXXX"
                  />
                  <ActionButton
                    label="Başqa nömrəyə göndər"
                    icon="send-outline"
                    variant="secondary"
                    onPress={() => handleSendWhatsApp(true)}
                    disabled={sending}
                  />
                </View>
              </View>

              <View style={styles.section}>
                <Text style={styles.sectionTitle}>Mənbə vəziyyəti</Text>
                <MetaRow label="Uğurlu mənbə" value={result?.forecast_meta.successful_sources.length || 0} />
                <MetaRow label="Namizəd pəncərə" value={result?.forecast_meta.candidate_window_count || 0} />
                <MetaRow label="Analiz günü" value={result?.input.analysis_days || 3} />
              </View>
            </>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: "#f4f7ef"
  },
  flex: {
    flex: 1
  },
  container: {
    padding: 18,
    paddingBottom: 40
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 18
  },
  eyebrow: {
    color: "#5b6d63",
    fontSize: 14,
    fontWeight: "700"
  },
  title: {
    color: "#17352f",
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800"
  },
  settingsButton: {
    width: 44,
    height: 44,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#e1ece6",
    borderWidth: 1,
    borderColor: "#b7cdc2"
  },
  settingsBox: {
    borderRadius: 8,
    padding: 14,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d7e0da",
    gap: 8,
    marginBottom: 14
  },
  helperText: {
    color: "#60766e",
    fontSize: 13,
    lineHeight: 18
  },
  form: {
    gap: 10,
    marginBottom: 14
  },
  label: {
    color: "#233f37",
    fontSize: 14,
    fontWeight: "700"
  },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: "#c9d6cd",
    borderRadius: 8,
    paddingHorizontal: 12,
    color: "#17352f",
    backgroundColor: "#ffffff",
    fontSize: 15
  },
  segment: {
    flexDirection: "row",
    borderWidth: 1,
    borderColor: "#c9d6cd",
    borderRadius: 8,
    overflow: "hidden",
    backgroundColor: "#ffffff"
  },
  segmentItem: {
    flex: 1,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 8
  },
  segmentItemActive: {
    backgroundColor: "#23685b"
  },
  segmentText: {
    color: "#426157",
    fontSize: 14,
    fontWeight: "700",
    textAlign: "center"
  },
  segmentTextActive: {
    color: "#ffffff"
  },
  button: {
    minHeight: 50,
    borderRadius: 8,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    gap: 8,
    backgroundColor: "#23685b",
    paddingHorizontal: 14
  },
  buttonSecondary: {
    backgroundColor: "#e1ece6",
    borderWidth: 1,
    borderColor: "#b7cdc2"
  },
  buttonDanger: {
    backgroundColor: "#a64033"
  },
  buttonDisabled: {
    opacity: 0.6
  },
  buttonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "800"
  },
  buttonSecondaryText: {
    color: "#17433a"
  },
  loadingBox: {
    borderRadius: 8,
    padding: 14,
    backgroundColor: "#ffffff",
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 12
  },
  loadingText: {
    color: "#315047",
    fontWeight: "700"
  },
  errorBox: {
    borderRadius: 8,
    padding: 14,
    backgroundColor: "#fbe9e7",
    marginBottom: 12
  },
  errorTitle: {
    color: "#8f2d23",
    fontWeight: "800",
    marginBottom: 4
  },
  errorText: {
    color: "#8f2d23",
    lineHeight: 20
  },
  summary: {
    borderRadius: 8,
    padding: 16,
    backgroundColor: "#dceee4",
    marginBottom: 12
  },
  summaryTitle: {
    color: "#17352f",
    fontSize: 18,
    fontWeight: "800",
    marginBottom: 8
  },
  summaryText: {
    color: "#27483f",
    lineHeight: 22,
    fontSize: 15
  },
  section: {
    borderRadius: 8,
    padding: 16,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#d7e0da",
    marginBottom: 12
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginBottom: 8
  },
  sectionTitle: {
    color: "#17352f",
    fontSize: 17,
    fontWeight: "800",
    marginBottom: 8
  },
  scorePill: {
    minWidth: 70,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
    alignItems: "center"
  },
  scoreText: {
    color: "#ffffff",
    fontWeight: "900"
  },
  scoreGood: {
    backgroundColor: "#1d7a55"
  },
  scoreCareful: {
    backgroundColor: "#b98022"
  },
  scoreBad: {
    backgroundColor: "#a64033"
  },
  scoreMuted: {
    backgroundColor: "#6f7f78"
  },
  windowTime: {
    color: "#17352f",
    fontSize: 21,
    lineHeight: 28,
    fontWeight: "900",
    marginBottom: 8
  },
  cardTitle: {
    color: "#244d43",
    fontWeight: "800",
    marginBottom: 6
  },
  bodyText: {
    color: "#334f47",
    fontSize: 15,
    lineHeight: 23
  },
  noteBlock: {
    marginTop: 12,
    gap: 7
  },
  noteText: {
    color: "#3e5b52",
    lineHeight: 21
  },
  altCard: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#dbe4de",
    padding: 12,
    marginTop: 8
  },
  altTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center"
  },
  altRank: {
    color: "#244d43",
    fontWeight: "800"
  },
  smallScore: {
    minWidth: 40,
    borderRadius: 8,
    paddingVertical: 4,
    alignItems: "center"
  },
  smallScoreText: {
    color: "#ffffff",
    fontWeight: "900"
  },
  altTime: {
    marginTop: 6,
    color: "#17352f",
    fontWeight: "800"
  },
  altReason: {
    marginTop: 5,
    color: "#3e5b52",
    lineHeight: 20
  },
  whatsappText: {
    color: "#17352f",
    lineHeight: 22,
    backgroundColor: "#f4f7ef",
    borderRadius: 8,
    padding: 12,
    marginBottom: 12
  },
  buttonStack: {
    gap: 10
  },
  metaRow: {
    minHeight: 34,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: "#edf1ee"
  },
  metaLabel: {
    color: "#60766e",
    fontWeight: "700"
  },
  metaValue: {
    color: "#17352f",
    fontWeight: "900"
  }
});
