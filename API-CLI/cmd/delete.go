package cmd

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"context"
	"fmt"
	"strings"

	"github.com/CesarAchig/api-cli/api"
	"github.com/CesarAchig/api-cli/config"
	"github.com/spf13/cobra"
)

//////////////////////////
//  Command Definition  //
//////////////////////////
var deleteCmd = &cobra.Command{
	Use:   "delete",
	Short: "Eliminar un dataset de la plataforma en la nube",
	Long: `Elimina permanentemente un dataset especificado de tu inventario en la nube.
Usa este comando para limpiar datasets antiguos que ya no son necesarios.

Nota: Esta acción es irreversible. Una vez que un dataset es eliminado,
no puede ser recuperado.`,
	RunE: deleteCmdRun,
}

//////////////////////////
//  Command Functions   //
//////////////////////////
func deleteCmdRun(cmd *cobra.Command, args []string) error {
	datasetName, err := cmd.Flags().GetString("dataset-name")
	if err != nil {
		return fmt.Errorf("Error obteniendo el flag --dataset-name: %w", err)
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

	ctx := context.Background()
	err = client.Delete(ctx, config.AppConfig.DeleteEndpoint, creds.Username, datasetName)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			return fmt.Errorf("El dataset '%s' no existe en tu inventario.", datasetName)
		}
		return fmt.Errorf("Error eliminando el dataset: %w", err)
	}

	fmt.Printf("Dataset '%s' eliminado correctamente.\n", datasetName)
	return nil
}

//////////////////////////
//    Init Function     //
//////////////////////////
func init() {
	deleteCmd.Flags().String("dataset-name", "", "Nombre del dataset que se eliminará")
	if err := deleteCmd.MarkFlagRequired("dataset-name"); err != nil {
		panic(err)
	}
	rootCmd.AddCommand(deleteCmd)
}
