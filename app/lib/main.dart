import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

const urlImpianti = 'https://brnlsn.github.io/scrabetone/impianti.json';
const urlCoords = 'https://brnlsn.github.io/scrabetone/coords.json';

void main() => runApp(const ScrabetoneApp());

class ScrabetoneApp extends StatelessWidget {
  const ScrabetoneApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Scrabetone',
      theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  List<Map<String, dynamic>> elementi = [];
  bool caricando = false;
  String? errore;

  Future<void> scaricaDati() async {
    setState(() {
      caricando = true;
      errore = null;
    });
    try {
      final results = await Future.wait([
        http.get(Uri.parse(urlImpianti)),
        http.get(Uri.parse(urlCoords)),
      ]);
      
      final rImpianti = results[0];
      final rCoords = results[1];

      if (rImpianti.statusCode != 200) throw Exception('Errore impianti: HTTP ${rImpianti.statusCode}');
      if (rCoords.statusCode != 200) throw Exception('Errore coords: HTTP ${rCoords.statusCode}');

      final dataImpianti = json.decode(utf8.decode(rImpianti.bodyBytes)) as Map<String, dynamic>;
      final dataCoords = json.decode(utf8.decode(rCoords.bodyBytes)) as Map<String, dynamic>;

      final lista = (dataImpianti['elementi'] as List).cast<Map<String, dynamic>>();
      
      // Unione dei dati tramite ID
      for (var el in lista) {
        final elId = el['id'] as String?;
        if (elId != null && dataCoords.containsKey(elId)) {
          final c = dataCoords[elId];
          el['lat'] = c['lat'];
          el['lon'] = c['lon'];
          if (c['geometry'] != null && (c['geometry'] as List).isNotEmpty) {
            el['geometry'] = c['geometry'];
          }
        }
      }

      setState(() {
        elementi = lista;
      });
    } catch (e) {
      setState(() => errore = e.toString());
    } finally {
      setState(() => caricando = false);
    }
  }

  List<Polyline> _costruisciPolilinee() {
    return elementi
        .where((e) => e['geometry'] != null && (e['geometry'] as List).isNotEmpty)
        .map((e) {
      final isAperto = e['stato'] == 'Aperto';
      final points = (e['geometry'] as List)
          .map((p) => LatLng(p[0] as double, p[1] as double))
          .toList();

      return Polyline(
        points: points,
        strokeWidth: 4.0,
        color: isAperto ? Colors.green : Colors.red,
      );
    }).toList();
  }

  List<Marker> _costruisciMarker() {
    return elementi
        .where((e) => e['geometry'] == null || (e['geometry'] as List).isEmpty)
        .map((e) {
      final isAperto = e['stato'] == 'Aperto';
      final isImpianto = e['tipo'] == 'Impianti';
      final lat = e['lat'] as double? ?? 44.145;
      final lon = e['lon'] as double? ?? 10.660;

      return Marker(
        point: LatLng(lat, lon),
        width: 30,
        height: 30,
        child: Icon(
          isImpianto ? Icons.cable : Icons.downhill_skiing,
          color: isAperto ? Colors.green : Colors.red,
          size: 30,
        ),
      );
    }).toList();
  }

  void mostraLista() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        minChildSize: 0.3,
        maxChildSize: 0.95,
        expand: false,
        builder: (ctx, scrollCtrl) =>
            _ListaElementi(elementi: elementi, scrollCtrl: scrollCtrl),
      ),
    );
  }

  @override
  void initState() {
    super.initState();
    scaricaDati();
  }

  @override
  Widget build(BuildContext context) {
    final aperti = elementi.where((e) => e['stato'] == 'Aperto').length;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scrabetone'),
        actions: [
          if (caricando)
            const Padding(
              padding: EdgeInsets.all(16),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            )
          else
            IconButton(icon: const Icon(Icons.refresh), onPressed: scaricaDati),
        ],
      ),
      body: Stack(
        children: [
          FlutterMap(
            options: const MapOptions(
              initialCenter: LatLng(44.145, 10.660),
              initialZoom: 14.0,
            ),
            children: [
              TileLayer(
                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.brnlsn.scrabetone_app',
              ),
              PolylineLayer(
                polylines: _costruisciPolilinee(),
              ),
              MarkerLayer(
                markers: _costruisciMarker(),
              ),
            ],
          ),
          if (errore != null)
            Positioned(
              top: 8,
              left: 8,
              right: 8,
              child: Material(
                color: Colors.red.shade100,
                child: Padding(
                  padding: const EdgeInsets.all(8),
                  child: Text('Errore: $errore'),
                ),
              ),
            ),
          Positioned(
            bottom: 16,
            left: 16,
            right: 16,
            child: FilledButton.icon(
              onPressed: elementi.isEmpty ? null : mostraLista,
              icon: const Icon(Icons.list),
              label: Text('${elementi.length} elementi — $aperti aperti'),
            ),
          ),
        ],
      ),
    );
  }
}

class _ListaElementi extends StatelessWidget {
  final List<Map<String, dynamic>> elementi;
  final ScrollController scrollCtrl;
  const _ListaElementi({required this.elementi, required this.scrollCtrl});

  @override
  Widget build(BuildContext context) {
    // Raggruppa per TIPO, poi per AREA
    final gruppi = <String, Map<String, List<Map<String, dynamic>>>>{};
    for (final e in elementi) {
      final tipo = e['tipo'] as String;
      final area = e['area'] as String;
      gruppi.putIfAbsent(tipo, () => {}).putIfAbsent(area, () => []).add(e);
    }

    final items = <Widget>[];
    
    // Ordina i tipi (Impianti, Piste...)
    final tipiOrdinati = gruppi.keys.toList()..sort();
    
    for (final tipo in tipiOrdinati) {
      items.add(Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
        child: Text(tipo, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
      ));

      final aree = gruppi[tipo]!;
      final areeOrdinate = aree.keys.toList()..sort();

      for (final area in areeOrdinate) {
        items.add(Padding(
          padding: const EdgeInsets.fromLTRB(24, 12, 16, 4),
          child: Text(area, style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Colors.blueGrey)),
        ));

        for (final e in aree[area]!) {
          final aperto = e['stato'] == 'Aperto';
          items.add(ListTile(
            contentPadding: const EdgeInsets.only(left: 32, right: 16),
            leading: Icon(
              aperto ? Icons.check_circle : Icons.cancel,
              color: aperto ? Colors.green : Colors.red,
            ),
            title: Text(e['nome'] as String),
            subtitle: Text(e['stato'] as String),
          ));
        }
      }
    }

    return ListView(controller: scrollCtrl, children: items);
  }
}