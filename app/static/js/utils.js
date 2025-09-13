// js/utils.js

/**
 * Busca dados da planilha Google via CSV
 * @param {string} sheetUrl - URL da planilha exportada como CSV
 * @returns {Promise<Array>} - Array de arrays com os dados
 */
export async function getData(sheetUrl) {
    console.log('Solicitando dados da planilha...');
    try {
        const response = await fetch(sheetUrl);
        if (!response.ok) {
            throw new Error(`Erro: ${response.status}`);
        }
        const csvText = await response.text();
        return parseCSV(csvText);
    } catch (error) {
        console.error('Erro ao buscar dados:', error);
        throw error;
    }
}

/**
 * Converte CSV em array de arrays
 * @param {string} csvText - Texto CSV
 * @returns {Array<Array<string>>}
 */
export function parseCSV(csvText) {
    return csvText.split('\n').map(row => row.split(','));
}
