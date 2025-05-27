{{/*
Common labels
*/}}
{{- define "scale-printer-mqtt.labels" -}}
helm.sh/chart: {{ include "scale-printer-mqtt.chart" . }}
{{ include "scale-printer-mqtt.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/*
Selector labels for a specific daemon (scale or printer)
Usage: {{ include "scale-printer-mqtt.daemonSelectorLabels" (dict "Chart" .Chart "daemonName" "scale-daemon") }}
*/}}
{{- define "scale-printer-mqtt.daemonSelectorLabels" -}}
app.kubernetes.io/name: {{ include "scale-printer-mqtt.name" .Chart }}-{{ .daemonName }}
app.kubernetes.io/instance: {{ .Chart.Release.Name }}
{{- end -}}


{{/*
Selector labels (generic for the chart, might need to be more specific per component)
*/}}
{{- define "scale-printer-mqtt.selectorLabels" -}}
app.kubernetes.io/name: {{ include "scale-printer-mqtt.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Create the name of the chart.
*/}}
{{- define "scale-printer-mqtt.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "scale-printer-mqtt.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "scale-printer-mqtt.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create the name for the service account to use
*/}}
{{- define "scale-printer-mqtt.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
    {{- default (include "scale-printer-mqtt.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
    {{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/*
Helper to get image for a daemon (scale or printer)
Usage: {{ include "scale-printer-mqtt.daemonImage" (dict "Values" .Values "daemonKey" "scaleDaemon") }}
*/}}
{{- define "scale-printer-mqtt.daemonImage" -}}
{{- $daemonConfig := get .Values .daemonKey -}}
{{- printf "%s:%s" $daemonConfig.image.repository ($daemonConfig.image.tag | default .Chart.AppVersion) -}}
{{- end -}}
