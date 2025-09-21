{{/*
Expand the name of the chart.
*/}}
{{- define "spacebridge.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "spacebridge.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "spacebridge.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "spacebridge.labels" -}}
helm.sh/chart: {{ include "spacebridge.chart" . }}
{{ include "spacebridge.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "spacebridge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "spacebridge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "spacebridge.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "spacebridge.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the database connection URL
*/}}
{{- define "spacebridge.databaseUrl" -}}
{{- if .Values.database.enabled -}}
{{- if .Values.database.external -}}
postgresql://{{ .Values.database.externalDatabase.user }}:{{ .Values.database.externalDatabase.password }}@{{ .Values.database.externalDatabase.host }}:{{ .Values.database.externalDatabase.port }}/{{ .Values.database.externalDatabase.database }}
{{- else -}}
postgresql://{{ .Values.database.cnpg.auth.username | default "postgres" }}:{{ .Values.database.cnpg.auth.password | default "" }}@{{ .Release.Name }}-{{ .Chart.Name }}-db-rw:5432/{{ .Values.database.cnpg.auth.database }}
{{- end -}}
{{- else -}}
{{ .Values.environment.databaseUrl }}
{{- end -}}
{{- end }}
