package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/CesarAchig/api-cli/api"
	"github.com/CesarAchig/api-cli/config"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var getPredictionCmd = &cobra.Command{
	Use:   "predict",
	Short: "Realizar una predicción usando un modelo entrenado",
	Long: `Envía un archivo CSV con características al endpoint de predicción
y devuelve el array de predicciones generado por el modelo entrenado.

El archivo CSV debe contener las columnas de características
que el modelo espera (sin la columna objetivo).`,
	RunE: predictRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func predictRun(cmd *cobra.Command, args []string) error {
	datasetName, err := cmd.Flags().GetString("dataset-name")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --dataset-name: %w", err)
	}
	featuresFile, err := cmd.Flags().GetString("features-file")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --features-file: %w", err)
	}

	// --- Validar que el archivo existe y es CSV ---
	info, err := os.Stat(featuresFile)
	if err != nil {
		if os.IsNotExist(err) {
			return fmt.Errorf("El archivo '%s' no existe", featuresFile)
		}
		return fmt.Errorf("Error al acceder al archivo '%s': %w", featuresFile, err)
	}
	if info.IsDir() {
		return fmt.Errorf("'%s' es un directorio, no un archivo", featuresFile)
	}
	ext := filepath.Ext(featuresFile)
	if ext != ".csv" {
		return fmt.Errorf("El archivo '%s' debe tener extensión .csv (extensión actual: '%s')", featuresFile, ext)
	}

	// --- Leer el archivo CSV ---
	csvBytes, err := os.ReadFile(featuresFile)
	if err != nil {
		return fmt.Errorf("Error leyendo el archivo '%s': %w", featuresFile, err)
	}

	creds, err := requireAuth()
	if err != nil {
		return err
	}

	if creds.SourceURL == "" {
		return fmt.Errorf("Error: no se encontró una URL de API guardada. Ejecuta 'login' primero")
	}
	client := api.NewClient(creds.SourceURL)
	client.AuthToken = creds.Token

	payload := map[string]interface{}{
		"user":         creds.Username,
		"datasetName":  datasetName,
		"features_csv": string(csvBytes),
	}

	ctx := context.Background()
	resp, err := client.PostJSON(ctx, config.AppConfig.PredictionEndpoint, payload)
	if err != nil {
		return fmt.Errorf("Error al obtener predicción: %w", err)
	}

	// --- Parsear JSON de respuesta ---
	var result struct {
		Predictions []interface{} `json:"predictions"`
	}
	if err := json.Unmarshal(resp, &result); err != nil {
		return fmt.Errorf("Error parseando respuesta JSON: %w", err)
	}
	if len(result.Predictions) == 0 {
		return fmt.Errorf("La respuesta no contiene predicciones")
	}

	// --- Detectar delimitador y parsear CSV original ---
	delimiter := _detectDelimiter(string(csvBytes))
	csvReader := csv.NewReader(strings.NewReader(string(csvBytes)))
	csvReader.Comma = delimiter
	records, err := csvReader.ReadAll()
	if err != nil {
		return fmt.Errorf("Error parseando CSV local: %w", err)
	}
	if len(records) == 0 {
		return fmt.Errorf("El archivo CSV está vacío")
	}

	// Añadir columna PREDICTION al header
	header := append(records[0], "PREDICTION")
	// Añadir predicción a cada fila de datos
	if len(records)-1 != len(result.Predictions) {
		return fmt.Errorf("Mismatch: CSV tiene %d filas de datos pero se recibieron %d predicciones", len(records)-1, len(result.Predictions))
	}
	var outputRecords [][]string
	outputRecords = append(outputRecords, header)
	for i, pred := range result.Predictions {
		row := append(records[i+1], fmt.Sprintf("%v", pred))
		outputRecords = append(outputRecords, row)
	}

	// --- Determinar destino de salida ---
	outFile, _ := cmd.Flags().GetString("out")

	var writer io.Writer
	if outFile != "" {
		f, err := os.Create(outFile)
		if err != nil {
			return fmt.Errorf("Error creando archivo de salida '%s': %w", outFile, err)
		}
		defer f.Close()
		writer = f
	} else {
		writer = os.Stdout
	}

	if outFile != "" {
		csvWriter := csv.NewWriter(writer)
		if err := csvWriter.WriteAll(outputRecords); err != nil {
			return fmt.Errorf("Error escribiendo CSV de salida: %w", err)
		}
		csvWriter.Flush()
		fmt.Printf("Resultado guardado en: %s\n", outFile)
	} else {
		// Mostrar como tabla ASCII en consola
		fmt.Println(_formatTable(outputRecords))
	}
	return nil
}

// _detectDelimiter analiza la primera línea del CSV para decidir si usa ';' o ','.
func _detectDelimiter(csvText string) rune {
	lines := strings.Split(csvText, "\n")
	if len(lines) == 0 {
		return ','
	}
	firstLine := lines[0]
	semicolons := strings.Count(firstLine, ";")
	commas := strings.Count(firstLine, ",")
	if semicolons > commas {
		return ';'
	}
	return ','
}

// _formatTable formatea un slice de slices de strings como una tabla ASCII.
func _formatTable(records [][]string) string {
	if len(records) == 0 {
		return ""
	}
	numCols := len(records[0])

	// Calcular ancho máximo de cada columna
	colWidths := make([]int, numCols)
	for _, row := range records {
		for i, cell := range row {
			if i < numCols && len(cell) > colWidths[i] {
				colWidths[i] = len(cell)
			}
		}
	}

	// Asegurar un ancho mínimo para legibilidad
	for i := range colWidths {
		if colWidths[i] < 3 {
			colWidths[i] = 3
		}
	}

	var sb strings.Builder
	separator := _buildSeparator(colWidths)

	sb.WriteString(separator)
	for i, row := range records {
		sb.WriteString("| ")
		for j, cell := range row {
			if j < numCols {
				fmt.Fprintf(&sb, "%-*s | ", colWidths[j], cell)
			}
		}
		sb.WriteString("\n")
		if i == 0 {
			sb.WriteString(separator)
		}
	}
	sb.WriteString(separator)

	return sb.String()
}

// _buildSeparator construye la línea separadora de la tabla.
func _buildSeparator(widths []int) string {
	var parts []string
	for _, w := range widths {
		parts = append(parts, strings.Repeat("-", w+2))
	}
	return "+" + strings.Join(parts, "+") + "+\n"
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	getPredictionCmd.Flags().String("dataset-name", "", "Nombre del dataset asociado al modelo entrenado")
	if err := getPredictionCmd.MarkFlagRequired("dataset-name"); err != nil {
		panic(err)
	}
	getPredictionCmd.Flags().String("features-file", "", "Ruta al archivo CSV con las características para la predicción")
	if err := getPredictionCmd.MarkFlagRequired("features-file"); err != nil {
		panic(err)
	}
	getPredictionCmd.Flags().String("out", "", "Ruta al archivo CSV de salida (opcional). Si se omite, se muestra por consola.")
	rootCmd.AddCommand(getPredictionCmd)
}
